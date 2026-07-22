"""Executable ALB/Cognito identity adapter and reverse proxy.

ALB authenticate-cognito -> this gateway :8080 -> app on 127.0.0.1:8081.
The ECS security group must expose only the gateway port.
"""
from __future__ import annotations
import json, os, threading, time, urllib.error, urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Callable
import jwt
from app.gateway import mint_gateway_assertion, resolve_role_binding, strip_client_auth_headers

class GatewayConfigurationError(RuntimeError): pass

class ALBIdentityVerifier:
    def __init__(self, *, region, expected_signer, expected_client, expected_issuer, key_loader: Callable[[str],str]|None=None, cache_seconds=3600):
        if not all((region,expected_signer,expected_client,expected_issuer)): raise GatewayConfigurationError('missing ALB verifier configuration')
        self.region=region; self.expected_signer=expected_signer; self.expected_client=expected_client; self.expected_issuer=expected_issuer
        self.key_loader=key_loader or self._fetch_key; self.cache_seconds=int(cache_seconds); self._keys={}; self._lock=threading.Lock()
    def _fetch_key(self,kid):
        if not kid or len(kid)>256 or not all(c.isalnum() or c in '-_' for c in kid): raise PermissionError('invalid ALB key id')
        url='https://public-keys.auth.elb.' + self.region + '.amazonaws.com/' + kid
        with urllib.request.urlopen(url,timeout=3) as response:
            if response.status!=200: raise PermissionError('ALB key unavailable')
            value=response.read(16384).decode('ascii')
        if 'PUBLIC KEY' not in value: raise PermissionError('invalid ALB key')
        return value
    def _key(self,kid):
        now=time.time()
        with self._lock:
            item=self._keys.get(kid)
            if item and item[0]>now:return item[1]
        value=self.key_loader(kid)
        with self._lock:self._keys[kid]=(now+self.cache_seconds,value)
        return value
    def verify(self,token,identity,now_epoch=None):
        try: header=jwt.get_unverified_header(token)
        except Exception as exc: raise PermissionError('invalid ALB token') from exc
        if header.get('alg')!='ES256' or header.get('signer')!=self.expected_signer or header.get('client')!=self.expected_client or header.get('iss')!=self.expected_issuer: raise PermissionError('unexpected ALB identity context')
        try:
            claims=jwt.decode(token,self._key(str(header.get('kid',''))),algorithms=['ES256'],options={'verify_aud':False,'verify_exp':False})
        except Exception as exc: raise PermissionError('invalid ALB identity signature') from exc
        subject=str(claims.get('sub','')).strip()
        if not subject or subject!=str(identity).strip(): raise PermissionError('ALB identity mismatch')
        try: expires=int(header.get('exp',claims.get('exp',0)))
        except (TypeError,ValueError) as exc: raise PermissionError('invalid ALB expiry') from exc
        if expires <= (int(time.time()) if now_epoch is None else int(now_epoch)): raise PermissionError('expired ALB token')
        return self.expected_issuer,subject

def load_role_bindings(raw):
    try:value=json.loads(raw)
    except Exception as exc:raise GatewayConfigurationError('invalid role bindings') from exc
    if not isinstance(value,dict) or not value:raise GatewayConfigurationError('role bindings must be non-empty')
    for principal,role in value.items():
        if not isinstance(principal,str) or not principal.startswith('oidc:') or role not in {'admin','reviewer','scanner'}:raise GatewayConfigurationError('invalid role binding')
    return value

def duplicate_identity_headers(message):
    return any(len(message.get_all(name,[]))!=1 for name in ('x-amzn-oidc-data','x-amzn-oidc-identity'))

class Handler(BaseHTTPRequestHandler):
    server_version='ProjectXRayGateway/1';sys_version=''
    def log_message(self,fmt,*args): print(json.dumps({'event':'gateway_request','path':self.path.split('?',1)[0],'message':fmt%args},separators=(',',':')))
    def reply(self,status,body,ctype='application/json; charset=utf-8'):
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.end_headers();self.wfile.write(body)
    def proxy(self):
        if self.path.split('?',1)[0]=='/health':
            try:
                with urllib.request.urlopen(self.server.upstream+'/health',timeout=2) as r:return self.reply(200 if r.status==200 else 503,r.read(4096))
            except Exception:return self.reply(503,b'{"status":"not_ready"}')
        if duplicate_identity_headers(self.headers):return self.reply(401,b'{"error":"unauthorized"}')
        try:
            issuer,subject=self.server.verifier.verify(self.headers.get('x-amzn-oidc-data',''),self.headers.get('x-amzn-oidc-identity',''))
            role=resolve_role_binding(self.server.bindings,issuer,subject)
            assertion=mint_gateway_assertion(issuer=issuer,subject=subject,role=role,secret=self.server.secret,key_id=self.server.key_id,audience=self.server.audience)
        except Exception:return self.reply(401,b'{"error":"unauthorized"}')
        try:length=int(self.headers.get('Content-Length','0') or '0')
        except ValueError:return self.reply(400,b'{"error":"invalid request"}')
        if length<0 or length>self.server.max_body:return self.reply(413,b'{"error":"request too large"}')
        body=self.rfile.read(length) if length else None; headers=strip_client_auth_headers(dict(self.headers.items()))
        for name in list(headers):
            if name.lower() in {'host','connection','proxy-connection','keep-alive','transfer-encoding','upgrade','x-amzn-oidc-data','x-amzn-oidc-identity','cookie'}:headers.pop(name,None)
        headers.update(assertion);request=urllib.request.Request(self.server.upstream+self.path,data=body,headers=headers,method=self.command)
        try:
            with urllib.request.urlopen(request,timeout=15) as r:return self.reply(r.status,r.read(self.server.max_response),r.headers.get('Content-Type','application/octet-stream'))
        except urllib.error.HTTPError as exc:return self.reply(exc.code,exc.read(self.server.max_response),exc.headers.get('Content-Type','application/json'))
        except Exception:return self.reply(502,b'{"error":"upstream unavailable"}')
    do_GET=proxy;do_POST=proxy

class Server(ThreadingHTTPServer):
    def __init__(self,address):
        region=os.getenv('AWS_REGION','ap-south-1');signer=os.getenv('ALB_SIGNER_ARN','');client=os.getenv('COGNITO_CLIENT_ID','');issuer=os.getenv('COGNITO_ISSUER','')
        self.secret=os.getenv('OIDC_PROXY_SECRET','');self.key_id=os.getenv('GATEWAY_ASSERTION_KEY_ID','');self.audience=os.getenv('GATEWAY_ASSERTION_AUDIENCE','project-xray-app')
        if len(self.secret)<32 or not self.key_id:raise GatewayConfigurationError('unsafe assertion signing configuration')
        self.verifier=ALBIdentityVerifier(region=region,expected_signer=signer,expected_client=client,expected_issuer=issuer);self.bindings=load_role_bindings(os.getenv('GATEWAY_ROLE_BINDINGS_JSON',''))
        self.upstream=os.getenv('APP_UPSTREAM','http://127.0.0.1:8081').rstrip('/');self.max_body=int(os.getenv('MAX_BODY_BYTES','2097152'));self.max_response=int(os.getenv('MAX_RESPONSE_BYTES','16777216'))
        super().__init__(address,Handler)
if __name__=='__main__': Server(('0.0.0.0',int(os.getenv('GATEWAY_PORT','8080')))).serve_forever()
