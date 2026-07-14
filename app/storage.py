import datetime,hashlib,hmac,os,urllib.parse,urllib.request

def _sign(key,msg):return hmac.new(key,msg.encode(),hashlib.sha256).digest()
def sigv4_headers(method,url,access_key,secret_key,region='ap-south-1',service='s3',now=None):
 now=now or datetime.datetime.now(datetime.timezone.utc);amzdate=now.strftime('%Y%m%dT%H%M%SZ');datestamp=now.strftime('%Y%m%d');u=urllib.parse.urlparse(url);canonical_uri=urllib.parse.quote(u.path or '/',safe='/-_.~');canonical_query='&'.join(f'{urllib.parse.quote(k,safe="-_.~")}={urllib.parse.quote(v,safe="-_.~")}' for k,v in sorted(urllib.parse.parse_qsl(u.query,keep_blank_values=True)));payload_hash=hashlib.sha256(b'').hexdigest();canonical_headers=f'host:{u.netloc}\nx-amz-content-sha256:{payload_hash}\nx-amz-date:{amzdate}\n';signed='host;x-amz-content-sha256;x-amz-date';canonical='\n'.join((method,canonical_uri,canonical_query,canonical_headers,signed,payload_hash));scope=f'{datestamp}/{region}/{service}/aws4_request';string='\n'.join(('AWS4-HMAC-SHA256',amzdate,scope,hashlib.sha256(canonical.encode()).hexdigest()));kd=_sign(('AWS4'+secret_key).encode(),datestamp) if False else hmac.new(('AWS4'+secret_key).encode(),datestamp.encode(),hashlib.sha256).digest();kr=hmac.new(kd,region.encode(),hashlib.sha256).digest();ks=hmac.new(kr,service.encode(),hashlib.sha256).digest();signing=hmac.new(ks,b'aws4_request',hashlib.sha256).digest();signature=hmac.new(signing,string.encode(),hashlib.sha256).hexdigest();auth=f'AWS4-HMAC-SHA256 Credential={access_key}/{scope}, SignedHeaders={signed}, Signature={signature}';return {'Host':u.netloc,'x-amz-date':amzdate,'x-amz-content-sha256':payload_hash,'Authorization':auth}
def parse_uri(uri,bucket):
 u=urllib.parse.urlparse(uri)
 if u.scheme!='s3' or u.netloc!=bucket or not u.path.lstrip('/'):raise ValueError('invalid managed storage URI')
 return u.path.lstrip('/')
def verify_managed_object(uri,expected_sha256,expected_size,endpoint=None,bucket=None,access_key=None,secret_key=None,region=None,timeout=5):
 endpoint=(endpoint or os.getenv('STORAGE_ENDPOINT','https://s3.amazonaws.com')).rstrip('/');bucket=bucket or os.getenv('STORAGE_BUCKET','');access_key=access_key or os.getenv('STORAGE_ACCESS_KEY','');secret_key=secret_key or os.getenv('STORAGE_SECRET_KEY','');region=region or os.getenv('STORAGE_REGION','ap-south-1');key=parse_uri(uri,bucket)
 if not access_key or not secret_key:raise RuntimeError('managed storage credentials missing')
 url=f'{endpoint}/{urllib.parse.quote(bucket,safe="")}/{urllib.parse.quote(key,safe="/-_.~")}';headers=sigv4_headers('HEAD',url,access_key,secret_key,region);req=urllib.request.Request(url,headers=headers,method='HEAD')
 with urllib.request.urlopen(req,timeout=timeout) as response:
  size=int(response.headers.get('Content-Length','-1'));sha=response.headers.get('x-amz-meta-sha256','').lower()
 if size!=int(expected_size) or sha!=expected_sha256.lower():raise RuntimeError('managed object metadata does not match evidence record')
 return {'uri':uri,'size_bytes':size,'sha256':sha}
