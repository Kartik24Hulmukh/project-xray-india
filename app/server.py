#!/usr/bin/env python3
import os,json,sqlite3,uuid,hashlib,re,time,secrets
from contextlib import contextmanager
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from datetime import datetime,timezone,timedelta
try:
 from app.security import token_hash,verify_proxy
 from app.audit import append as append_audit,verify as verify_audit
 from app.storage import verify_managed_object
 from app.operations import send_alert
except ModuleNotFoundError:
 from security import token_hash,verify_proxy
 from audit import append as append_audit,verify as verify_audit
 from storage import verify_managed_object
 from operations import send_alert

ROOT=Path(__file__).resolve().parents[1];DB=Path(os.getenv('DB_PATH',str(ROOT/'data/project_xray.db')))
PORT=int(os.getenv('PORT','8080'));MAX=int(os.getenv('MAX_BODY_BYTES','2097152'));ENV=os.getenv('APP_ENV','development')
PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL','http://localhost:8080');RATE_LIMIT=int(os.getenv('WRITE_RATE_LIMIT','60'));RATE={};METRICS={'requests':0,'errors':0,'writes':0,'auth_failures':0,'publications':0}
TOKEN_PEPPER=os.getenv('TOKEN_PEPPER','development-token-pepper-not-for-production');AUDIT_KEY=os.getenv('AUDIT_HMAC_KEY','development-audit-key-not-for-production');OIDC_SECRET=os.getenv('OIDC_PROXY_SECRET','');BACKUP_KEY=os.getenv('BACKUP_HMAC_KEY','')
ADMIN_TOKEN=os.getenv('ADMIN_TOKEN','change-before-deploy');REVIEWER_TOKENS={k:v for k,v in (x.split(':',1) for x in os.getenv('REVIEWER_TOKENS','').split(',') if ':' in x)};SCANNER_TOKENS={k:v for k,v in (x.split(':',1) for x in os.getenv('SCANNER_TOKENS','').split(',') if ':' in x)}
CLAIM_TYPES={'verified_fact','reported_allegation','official_claim','expert_assessment','data_inconsistency','audit_finding','court_finding'};PUBLIC_STATES={'published','disputed','corrected','withdrawn'};ID_RE=re.compile(r'^[a-z]{3}_[a-f0-9]{16}$')

def now():return datetime.now(timezone.utc).isoformat()
def uid(prefix):return prefix+'_'+uuid.uuid4().hex[:16]
def connect(path=None):
 p=Path(path or DB);p.parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(p,timeout=10,check_same_thread=False);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=5000');return c
@contextmanager
def db(write=False):
 c=connect()
 try:
  if write:c.execute('BEGIN IMMEDIATE')
  yield c
  if write:c.commit()
 except Exception:
  if write:c.rollback()
  raise
 finally:c.close()
def bootstrap(c,principal,role,secret,ttl=86400):
 if not secret or secret.startswith('change-'):return
 created=now();expires=(datetime.now(timezone.utc)+timedelta(seconds=ttl)).isoformat();h=token_hash(secret,TOKEN_PEPPER)
 c.execute('INSERT OR IGNORE INTO auth_tokens(id,principal,role,token_hash,expires_at,created_at) VALUES(?,?,?,?,?,?)',(uid('tok'),principal,role,h,expires,created))
def init():
 if ENV=='production':
  required=[('PUBLIC_BASE_URL',PUBLIC_BASE_URL.startswith('https://')),('TOKEN_PEPPER',len(TOKEN_PEPPER)>=32),('AUDIT_HMAC_KEY',len(AUDIT_KEY)>=32),('BACKUP_HMAC_KEY',len(BACKUP_KEY)>=32),('OIDC_PROXY_SECRET',len(OIDC_SECRET)>=32),('OBJECT_STORAGE_MODE',os.getenv('OBJECT_STORAGE_MODE')=='managed'),('STORAGE_BUCKET',bool(os.getenv('STORAGE_BUCKET'))),('STORAGE_ACCESS_KEY',bool(os.getenv('STORAGE_ACCESS_KEY'))),('STORAGE_SECRET_KEY',bool(os.getenv('STORAGE_SECRET_KEY'))),('MONITORING_WEBHOOK_URL',bool(os.getenv('MONITORING_WEBHOOK_URL'))),('MONITORING_WEBHOOK_SECRET',len(os.getenv('MONITORING_WEBHOOK_SECRET',''))>=32)]
  missing=[name for name,ok in required if not ok]
  if missing:raise RuntimeError('production configuration missing/unsafe: '+','.join(missing))
 with db(True) as c:
  legacy=c.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='sources'").fetchone()
  if legacy and c.execute('PRAGMA user_version').fetchone()[0] not in (0,3):raise RuntimeError('database migration required; run scripts/migrate_v2_to_v3.py')
  c.executescript((ROOT/'db/schema.sql').read_text())
  ttl=int(os.getenv('BOOTSTRAP_TOKEN_TTL_SECONDS','86400'));bootstrap(c,'admin','admin',ADMIN_TOKEN,ttl)
  for principal,secret in REVIEWER_TOKENS.items():bootstrap(c,principal,'reviewer',secret,ttl)
  for principal,secret in SCANNER_TOKENS.items():bootstrap(c,principal,'scanner',secret,ttl)
  verify_audit(c,AUDIT_KEY)
def audit(c,actor,action,typ,oid,detail=''):append_audit(c,uid('evt'),actor,action,typ,oid,detail,now(),AUDIT_KEY)
def auth(headers):
 if ENV=='production':return verify_proxy(headers,OIDC_SECRET)
 raw=headers.get('Authorization','');token=raw[7:] if raw.startswith('Bearer ') else ''
 if not token:return (None,None)
 h=token_hash(token,TOKEN_PEPPER);current=now()
 with db() as c:
  r=c.execute("SELECT role,principal FROM auth_tokens WHERE token_hash=? AND revoked_at='' AND expires_at>?",(h,current)).fetchone()
 return (r['role'],r['principal']) if r else (None,None)
def clean(value,limit,required=False):
 if not isinstance(value,str):raise ValueError('expected string')
 value=value.strip()
 if required and not value:raise ValueError('required field is empty')
 if len(value)>limit:raise ValueError(f'field exceeds {limit} characters')
 return value
def valid_id(value,prefix=None):return bool(ID_RE.fullmatch(value)) and (not prefix or value.startswith(prefix+'_'))
def rows(cur):return [dict(r) for r in cur.fetchall()]
def source(c,sid):return c.execute('SELECT * FROM sources WHERE id=?',(sid,)).fetchone()
def source_publishable(c,sid):
 docs=rows(c.execute('SELECT storage_state FROM documents WHERE source_id=?',(sid,)))
 return not docs or all(d['storage_state']=='clean' for d in docs)
def bundle(pid,private=False):
 with db() as c:
  p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
  if not p or (not private and p['status']!='published'):return None
  q='SELECT c.*,s.url source_url,s.publisher,s.retrieved_at,s.sha256 source_sha256 FROM claims c JOIN sources s ON s.id=c.source_id WHERE c.project_id=?';args=[pid]
  if not private:q+=' AND c.publication_state IN (?,?,?,?)';args+=sorted(PUBLIC_STATES)
  result={'project':dict(p),'claims':rows(c.execute(q+' ORDER BY c.created_at',args)),'gaps':rows(c.execute('SELECT * FROM gaps WHERE project_id=? ORDER BY created_at',(pid,))),'responses':rows(c.execute('SELECT r.*,s.url source_url FROM responses r LEFT JOIN sources s ON s.id=r.source_id WHERE r.project_id=? ORDER BY r.created_at',(pid,)))}
  if private:result.update({'sources':rows(c.execute('SELECT * FROM sources WHERE project_id=?',(pid,))),'documents':rows(c.execute('SELECT * FROM documents WHERE project_id=?',(pid,)))})
  return result

def strict_json(raw):
 def pairs(values):
  out={}
  for k,v in values:
   if k in out:raise ValueError('duplicate JSON key')
   out[k]=v
  return out
 return json.loads(raw,object_pairs_hook=pairs)

class H(BaseHTTPRequestHandler):
 server_version='ProjectXRay/0.3';sys_version=''
 def setup(self):super().setup();self.request.settimeout(15);self.request_id=''
 def log_message(self,fmt,*args):print(json.dumps({'time':now(),'request_id':self.request_id,'remote':self.client_address[0],'message':fmt%args},separators=(',',':')))
 def common(self,code,ctype):
  self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");self.send_header('Cache-Control','no-store');self.send_header('X-Request-ID',self.request_id)
  if PUBLIC_BASE_URL.startswith('https://'):self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
  self.end_headers()
 def out(self,obj,code=200):
  if code>=400:METRICS['errors']+=1
  body=json.dumps(obj,ensure_ascii=False,separators=(',',':'))
  if 200<=code<300 and getattr(self,'idem',None):
   c=getattr(self,'tx',None)
   if c:c.execute("UPDATE idempotency_keys SET state='completed',response_code=?,response_body=?,completed_at=? WHERE principal=? AND key=?",(code,body,now(),self.idem[0],self.idem[1]))
  self.common(code,'application/json; charset=utf-8');self.wfile.write(body.encode())
 def text(self,value,code=200,ctype='text/plain; charset=utf-8'):self.common(code,ctype);self.wfile.write(value.encode())
 def body(self):
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ValueError('invalid Content-Length')
  if n<=0:raise ValueError('JSON body required')
  if n>MAX:raise OverflowError('request too large')
  if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise TypeError('Content-Type must be application/json')
  try:return strict_json(self.rfile.read(n))
  except json.JSONDecodeError:raise ValueError('invalid JSON')
 def principal(self,roles):
  role,actor=auth(self.headers)
  if role not in roles:METRICS['auth_failures']+=1;self.out({'error':'unauthorized'},401);return None
  return role,actor
 def limited(self):
  key=self.client_address[0];minute=int(time.time()//60);slot=RATE.setdefault((key,minute),0);RATE[(key,minute)]=slot+1
  for old in [k for k in RATE if k[1]<minute-1]:RATE.pop(old,None)
  return slot>=RATE_LIMIT
 def reserve_idempotency(self,actor,data):
  key=self.headers.get('Idempotency-Key','').strip()
  if ENV=='production' and not key:self.out({'error':'Idempotency-Key required'},400);return False
  if not key:return True
  if len(key)>128:self.out({'error':'invalid Idempotency-Key'},400);return False
  rh=hashlib.sha256((self.command+'|'+urlparse(self.path).path+'|'+json.dumps(data,sort_keys=True,separators=(',',':'))).encode()).hexdigest()
  with db(True) as c:
   old=c.execute('SELECT * FROM idempotency_keys WHERE principal=? AND key=?',(actor,key)).fetchone()
   if old:
    if old['request_hash']!=rh:self.out({'error':'idempotency key reused with different request'},409);return False
    if old['state']=='completed':self.common(old['response_code'],'application/json; charset=utf-8');self.wfile.write(old['response_body'].encode());return False
    self.out({'error':'request with this idempotency key is processing'},409);return False
   c.execute('INSERT INTO idempotency_keys(principal,key,request_hash,state,created_at) VALUES(?,?,?,?,?)',(actor,key,rh,'processing',now()))
  self.idem=(actor,key);return True
 def do_GET(self):
  METRICS['requests']+=1;self.request_id=self.headers.get('X-Request-ID') or uid('req');u=urlparse(self.path);path=u.path;query=parse_qs(u.query)
  if path=='/health':return self.out({'status':'ok','time':now(),'version':'0.3.0'})
  if path=='/ready':
   try:
    with db() as c:c.execute('SELECT 1');verify_audit(c,AUDIT_KEY)
    return self.out({'status':'ready','time':now()})
   except Exception:return self.out({'status':'not_ready'},503)
  if path=='/metrics':
   if not self.principal(('admin',)):return
   return self.text('\n'.join(f'project_xray_{k}_total {v}' for k,v in METRICS.items())+'\n',ctype='text/plain; version=0.0.4')
  if path=='/api/auth/tokens':
   if not self.principal(('admin',)):return
   with db() as c:return self.out({'tokens':rows(c.execute("SELECT id,principal,role,expires_at,revoked_at,created_at,rotated_from FROM auth_tokens ORDER BY created_at"))})
  if path=='/api/projects':
   private=query.get('include_private')==['1'] and auth(self.headers)[0] in ('admin','reviewer')
   with db() as c:q='SELECT id,title,authority,location,summary,status,synthetic,created_at,updated_at FROM projects'+('' if private else " WHERE status='published'");return self.out({'projects':rows(c.execute(q+' ORDER BY updated_at DESC'))})
  seg=[x for x in path.split('/') if x]
  if len(seg)>=3 and seg[:2]==['api','projects'] and valid_id(seg[2],'prj'):
   private=query.get('include_private')==['1'] and auth(self.headers)[0] in ('admin','reviewer');b=bundle(seg[2],private)
   if not b:return self.out({'error':'not found'},404)
   if len(seg)==3:return self.out(b)
   if len(seg)==4 and seg[3]=='report':
    p=b['project'];lines=[f"# Evidence report: {p['title']}",'',f'Generated: {now()}',f"Authority: {p['authority']}",'','## Claims']
    for x in b['claims']:lines += [f"- [{x['claim_type']} / {x['publication_state']}] {x['text']}",f"  Source: {x['source_url']} (retrieved {x['retrieved_at']}; SHA-256 {x['source_sha256']})",f"  Anchor: {x['page_ref'] or x['passage']}"]
    lines += ['','## Records not located']+[f"- {g['document_name']} — searched: {g['search_scope']} ({g['searched_at']})" for g in b['gaps']];return self.text('\n'.join(lines),ctype='text/markdown; charset=utf-8')
   if len(seg)==4 and seg[3]=='rti':
    p=b['project'];items='\n'.join(f"{i+1}. Certified electronic copy of {g['document_name']}." for i,g in enumerate(b['gaps'])) or '1. No document gaps have been selected.';return self.text(f"Draft RTI request — not legal advice\n\nTo: Public Information Officer, {p['authority']}\nSubject: Records concerning {p['title']}\n\nPlease provide:\n{items}\n")
   if len(seg)==4 and seg[3]=='audit':
    if not self.principal(('admin','reviewer')):return
    with db() as c:return self.out({'events':rows(c.execute("SELECT * FROM audit_events WHERE object_id=? OR detail LIKE ? ORDER BY id",(seg[2],'%project='+seg[2]+'%'))),'verification':verify_audit(c,AUDIT_KEY)})
  return self.static(path)
 def static(self,path):
  mapping={'/':'static/index.html','/index.html':'static/index.html','/app.js':'static/app.js','/styles.css':'static/styles.css'};rel=mapping.get(path)
  if not rel:return self.out({'error':'not found'},404)
  p=ROOT/rel;types={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8'};self.common(200,types[p.suffix]);self.wfile.write(p.read_bytes())
 def do_POST(self):
  METRICS['requests']+=1;METRICS['writes']+=1;self.request_id=self.headers.get('X-Request-ID') or uid('req');self.tx=None;self.idem=None
  if self.limited():return self.out({'error':'rate limit exceeded'},429)
  principal=self.principal(('admin','reviewer','scanner'))
  if not principal:return
  role,actor=principal
  try:data=self.body()
  except OverflowError as e:return self.out({'error':str(e)},413)
  except (ValueError,TypeError) as e:return self.out({'error':str(e)},400)
  if not self.reserve_idempotency(actor,data):return
  path=urlparse(self.path).path;seg=[x for x in path.split('/') if x]
  try:
   if path=='/api/operations/test-alert':
    if role!='admin':return self.out({'error':'admin required'},403)
    receipt=send_alert({'severity':'test','summary':'Project X-Ray monitoring path test','request_id':self.request_id})
    with db(True) as c:
     self.tx=c;audit(c,actor,'test','monitoring_alert',receipt['event_id']);return self.out({'delivered':True,'event_id':receipt['event_id']})
   with db(True) as c:
    self.tx=c
    if path=='/api/auth/tokens':
     if role!='admin':return self.out({'error':'admin required'},403)
     principal_name=clean(data.get('principal',''),120,True);new_role=data.get('role');ttl=int(data.get('ttl_seconds',3600))
     if new_role not in ('admin','reviewer','scanner') or not 60<=ttl<=2592000:return self.out({'error':'invalid role or ttl'},400)
     secret=secrets.token_urlsafe(32);tid=uid('tok');expires=(datetime.now(timezone.utc)+timedelta(seconds=ttl)).isoformat();rotated=data.get('rotated_from') or None
     if rotated and not c.execute("SELECT 1 FROM auth_tokens WHERE id=? AND revoked_at=''",(rotated,)).fetchone():return self.out({'error':'rotation source not active'},409)
     c.execute('INSERT INTO auth_tokens(id,principal,role,token_hash,expires_at,created_at,rotated_from) VALUES(?,?,?,?,?,?,?)',(tid,principal_name,new_role,token_hash(secret,TOKEN_PEPPER),expires,now(),rotated))
     if rotated:c.execute('UPDATE auth_tokens SET revoked_at=? WHERE id=?',(now(),rotated))
     audit(c,actor,'rotate' if rotated else 'create','auth_token',tid);return self.out({'id':tid,'token':secret,'expires_at':expires},201)
    if len(seg)==5 and seg[:3]==['api','auth','tokens'] and seg[4]=='revoke':
     if role!='admin':return self.out({'error':'admin required'},403)
     changed=c.execute("UPDATE auth_tokens SET revoked_at=? WHERE id=? AND revoked_at=''",(now(),seg[3])).rowcount
     if not changed:return self.out({'error':'active token not found'},404)
     audit(c,actor,'revoke','auth_token',seg[3]);return self.out({'id':seg[3],'revoked':True})
    if path=='/api/projects':
     if role!='admin':return self.out({'error':'admin required'},403)
     pid=uid('prj');t=now();c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)',(pid,clean(data.get('title',''),200,True),clean(data.get('authority',''),200),clean(data.get('location',''),200),clean(data.get('summary',''),4000),data.get('status','research'),int(bool(data.get('synthetic',False))),t,t));audit(c,actor,'create','project',pid);return self.out({'id':pid},201)
    if len(seg)<4 or seg[:2]!=['api','projects'] or not valid_id(seg[2],'prj'):return self.out({'error':'not found'},404)
    pid,kind=seg[2],seg[3]
    if not c.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():return self.out({'error':'project not found'},404)
    if kind=='sources' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     url=clean(data.get('url',''),2000,True);sha=clean(data.get('sha256',''),64,True).lower()
     if not url.startswith(('https://','http://')) or not re.fullmatch(r'[a-f0-9]{64}',sha):return self.out({'error':'valid source URL and SHA-256 required'},400)
     sid=uid('src');c.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,pid,clean(data.get('publisher',''),200,True),url,clean(data.get('source_class','official'),50,True),clean(data.get('retrieved_at',now()),64,True),sha,clean(data.get('passage',''),4000),clean(data.get('page_ref',''),100),now()));audit(c,actor,'create','source',sid,'project='+pid);return self.out({'id':sid},201)
    if kind=='documents' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     sha=clean(data.get('sha256',''),64,True).lower();media=clean(data.get('media_type',''),100,True);size=int(data.get('size_bytes',-1));sid=data.get('source_id') or None;uri=clean(data.get('storage_uri',''),1000)
     if not re.fullmatch(r'[a-f0-9]{64}',sha) or media not in {'application/pdf','text/plain','text/csv','application/json','image/png','image/jpeg'} or not 0<=size<=MAX:return self.out({'error':'invalid document metadata'},400)
     if sid and not source(c,sid):return self.out({'error':'source not found'},400)
     if ENV=='production':
      if not uri.startswith('s3://'+os.getenv('STORAGE_BUCKET','')+'/'):return self.out({'error':'managed storage URI required'},400)
      try:verify_managed_object(uri,sha,size)
      except Exception as e:return self.out({'error':'managed object verification failed','detail':str(e)},409)
     did=uid('doc');c.execute('INSERT INTO documents(id,project_id,source_id,filename,media_type,size_bytes,sha256,storage_state,scan_result,storage_uri,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(did,pid,sid,clean(data.get('filename',''),255,True),media,size,sha,'quarantined','pending',uri,now()));audit(c,actor,'create','document',did,'project='+pid);return self.out({'id':did,'storage_state':'quarantined'},201)
    if kind=='documents' and len(seg)==6 and valid_id(seg[4],'doc') and seg[5]=='scan':
     if role!='scanner':return self.out({'error':'scanner role required'},403)
     result=data.get('result');state='clean' if result=='clean' else 'rejected' if result=='malicious' else None
     if not state:return self.out({'error':'scan result must be clean or malicious'},400)
     changed=c.execute("UPDATE documents SET storage_state=?,scan_result=?,scanned_at=?,scanned_by=? WHERE id=? AND project_id=? AND storage_state='quarantined'",(state,result,now(),actor,seg[4],pid)).rowcount
     if not changed:return self.out({'error':'quarantined document not found'},409)
     audit(c,actor,'scan','document',seg[4],result);return self.out({'id':seg[4],'storage_state':state})
    if kind=='claims' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     ct=data.get('claim_type');sid=data.get('source_id','');text=clean(data.get('text',''),8000,True);passage=clean(data.get('passage',''),4000);page=clean(data.get('page_ref',''),100)
     if data.get('publication_state','candidate')!='candidate' or ct not in CLAIM_TYPES or not source(c,sid) or not (passage or page):return self.out({'error':'candidate with valid type, source and anchor required'},400)
     cid=uid('clm');t=now();c.execute('INSERT INTO claims(id,project_id,source_id,claim_type,publication_state,text,passage,page_ref,created_by,version,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',(cid,pid,sid,ct,'candidate',text,passage,page,actor,1,t,t));audit(c,actor,'create','claim',cid,'project='+pid);return self.out({'id':cid,'version':1,'publication_state':'candidate'},201)
    if kind=='claims' and len(seg)==6 and valid_id(seg[4],'clm') and seg[5]=='reviews':
     if role!='reviewer':return self.out({'error':'reviewer role required'},403)
     claim=c.execute('SELECT * FROM claims WHERE id=? AND project_id=?',(seg[4],pid)).fetchone();decision=data.get('decision')
     if not claim:return self.out({'error':'claim not found'},404)
     if claim['created_by']==actor:return self.out({'error':'creator cannot review own claim'},409)
     if decision not in ('approve','reject'):return self.out({'error':'invalid decision'},400)
     rid=uid('rev');c.execute('INSERT INTO claim_reviews VALUES(?,?,?,?,?,?,?)',(rid,seg[4],claim['version'],actor,decision,clean(data.get('note',''),1000),now()));approvals=c.execute("SELECT COUNT(*) n FROM claim_reviews WHERE claim_id=? AND claim_version=? AND decision='approve'",(seg[4],claim['version'])).fetchone()['n'];state='reviewed' if approvals>=2 else 'candidate';c.execute('UPDATE claims SET publication_state=?,updated_at=? WHERE id=?',(state,now(),seg[4]));audit(c,actor,'review','claim',seg[4],f'version={claim["version"]};{decision}');return self.out({'id':rid,'version':claim['version'],'approvals':approvals,'publication_state':state},201)
    if kind=='claims' and len(seg)==6 and valid_id(seg[4],'clm') and seg[5]=='publish':
     if role!='admin':return self.out({'error':'admin required'},403)
     verify_audit(c,AUDIT_KEY);claim=c.execute('SELECT * FROM claims WHERE id=? AND project_id=?',(seg[4],pid)).fetchone()
     if not claim:return self.out({'error':'claim not found'},404)
     approvals=c.execute("SELECT COUNT(DISTINCT reviewer) n FROM claim_reviews WHERE claim_id=? AND claim_version=? AND decision='approve'",(seg[4],claim['version'])).fetchone()['n']
     if approvals<2:return self.out({'error':'two current-version approvals required'},409)
     if not source_publishable(c,claim['source_id']):return self.out({'error':'source document remains quarantined or rejected'},409)
     if claim['publication_state'] in PUBLIC_STATES:return self.out({'id':seg[4],'version':claim['version'],'publication_state':claim['publication_state']})
     state='corrected' if claim['version']>1 else 'published';c.execute('UPDATE claims SET publication_state=?,updated_at=? WHERE id=?',(state,now(),seg[4]));audit(c,actor,'publish','claim',seg[4],f'project={pid};version={claim["version"]}');METRICS['publications']+=1;return self.out({'id':seg[4],'version':claim['version'],'publication_state':state})
    if kind=='claims' and len(seg)==6 and valid_id(seg[4],'clm') and seg[5]=='correct':
     if role!='admin':return self.out({'error':'admin required'},403)
     claim=c.execute('SELECT * FROM claims WHERE id=? AND project_id=?',(seg[4],pid)).fetchone();new_text=clean(data.get('text',''),8000,True);reason=clean(data.get('reason',''),1000,True)
     if not claim or claim['publication_state'] not in PUBLIC_STATES:return self.out({'error':'only public claims can be corrected'},409)
     if new_text==claim['text']:return self.out({'error':'correction must change text'},400)
     version=claim['version']+1;rid=uid('crv');c.execute('INSERT INTO claim_revisions VALUES(?,?,?,?,?,?,?,?,?)',(rid,seg[4],claim['version'],version,claim['text'],new_text,reason,actor,now()));c.execute("UPDATE claims SET text=?,version=?,publication_state='candidate',updated_at=? WHERE id=?",(new_text,version,now(),seg[4]));audit(c,actor,'correct','claim',seg[4],f'version={version};{reason}');return self.out({'id':seg[4],'revision_id':rid,'version':version,'publication_state':'candidate'})
    if kind=='gaps' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     gid=uid('gap');c.execute('INSERT INTO gaps VALUES(?,?,?,?,?,?,?)',(gid,pid,clean(data.get('document_name',''),300,True),clean(data.get('search_scope',''),2000,True),clean(data.get('searched_at',now()),64,True),data.get('status','not_located'),now()));audit(c,actor,'create','gap',gid,'project='+pid);return self.out({'id':gid},201)
    if kind=='responses' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     sid=data.get('source_id') or None
     if sid and not source(c,sid):return self.out({'error':'source not found'},400)
     rid=uid('rsp');c.execute('INSERT INTO responses VALUES(?,?,?,?,?,?)',(rid,pid,clean(data.get('responder',''),200,True),clean(data.get('text',''),8000,True),sid,now()));audit(c,actor,'create','response',rid,'project='+pid);return self.out({'id':rid},201)
    if kind=='publish' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     verify_audit(c,AUDIT_KEY);pending=c.execute("SELECT COUNT(*) n FROM claims WHERE project_id=? AND publication_state NOT IN ('published','disputed','corrected','withdrawn')",(pid,)).fetchone()['n'];published=c.execute("SELECT COUNT(*) n FROM claims WHERE project_id=? AND publication_state IN ('published','corrected')",(pid,)).fetchone()['n'];bad=c.execute("SELECT COUNT(*) n FROM claims c JOIN documents d ON d.source_id=c.source_id WHERE c.project_id=? AND d.storage_state!='clean'",(pid,)).fetchone()['n']
     if pending or not published or bad:return self.out({'error':'project has pending claims or non-clean evidence'},409)
     c.execute("UPDATE projects SET status='published',updated_at=? WHERE id=?",(now(),pid));audit(c,actor,'publish','project',pid);return self.out({'id':pid,'status':'published'})
    return self.out({'error':'not found'},404)
  except sqlite3.IntegrityError as e:return self.out({'error':'conflict','detail':str(e)},409)
  except (ValueError,TypeError) as e:return self.out({'error':str(e)},400)
  finally:self.tx=None

if __name__=='__main__':
 init();print(json.dumps({'event':'startup','service':'project-xray','version':'0.3.0','port':PORT,'environment':ENV}));ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
