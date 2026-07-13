#!/usr/bin/env python3
import os,json,sqlite3,uuid,hashlib,hmac,re,time
from contextlib import contextmanager
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from urllib.parse import urlparse,parse_qs
from pathlib import Path
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[1]
DB=Path(os.getenv('DB_PATH',str(ROOT/'data/project_xray.db')))
PORT=int(os.getenv('PORT','8080')); MAX=int(os.getenv('MAX_BODY_BYTES','2097152'))
ADMIN_TOKEN=os.getenv('ADMIN_TOKEN','change-before-deploy')
REVIEWER_TOKENS={k:v for k,v in (x.split(':',1) for x in os.getenv('REVIEWER_TOKENS','').split(',') if ':' in x)}
ENV=os.getenv('APP_ENV','development'); PUBLIC_BASE_URL=os.getenv('PUBLIC_BASE_URL','http://localhost:8080')
CLAIM_TYPES={'verified_fact','reported_allegation','official_claim','expert_assessment','data_inconsistency','audit_finding','court_finding'}
PUBLIC_STATES={'published','disputed','corrected','withdrawn'}
ID_RE=re.compile(r'^[a-z]{3}_[a-f0-9]{16}$')
RATE={}; RATE_LIMIT=int(os.getenv('WRITE_RATE_LIMIT','60'))

def now():return datetime.now(timezone.utc).isoformat()
def uid(prefix):return prefix+'_'+uuid.uuid4().hex[:16]
def connect(path=None):
 p=Path(path or DB);p.parent.mkdir(parents=True,exist_ok=True)
 c=sqlite3.connect(p,timeout=10);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON');c.execute('PRAGMA busy_timeout=5000');return c
@contextmanager
def db():
 c=connect()
 try:
  with c:yield c
 finally:c.close()
def init():
 if ENV=='production':
  if ADMIN_TOKEN in ('','change-before-deploy') or len(ADMIN_TOKEN)<24:raise RuntimeError('production requires a strong ADMIN_TOKEN')
  if not PUBLIC_BASE_URL.startswith('https://'):raise RuntimeError('production requires an HTTPS PUBLIC_BASE_URL')
 with db() as c:c.executescript((ROOT/'db/schema.sql').read_text())
def rows(cur):return [dict(x) for x in cur.fetchall()]
def digest(value):return hashlib.sha256(value.encode()).hexdigest()
def audit(c,actor,action,typ,oid,detail=''):
 prev=c.execute('SELECT event_hash FROM audit_events ORDER BY id DESC LIMIT 1').fetchone();previous=prev['event_hash'] if prev else ''
 eid=uid('evt');created=now();event_hash=digest('|'.join((previous,eid,actor,action,typ,oid,detail,created)))
 c.execute('INSERT INTO audit_events(event_id,actor,action,object_type,object_id,detail,previous_hash,event_hash,created_at) VALUES(?,?,?,?,?,?,?,?,?)',(eid,actor,action,typ,oid,detail,previous,event_hash,created))
def auth(headers):
 raw=headers.get('Authorization','');token=raw[7:] if raw.startswith('Bearer ') else ''
 if ADMIN_TOKEN not in ('','change-before-deploy') and hmac.compare_digest(token,ADMIN_TOKEN):return ('admin','admin')
 for reviewer,secret in REVIEWER_TOKENS.items():
  if secret and hmac.compare_digest(token,secret):return ('reviewer',reviewer)
 return (None,None)
def valid_id(value,prefix=None):return bool(ID_RE.fullmatch(value)) and (not prefix or value.startswith(prefix+'_'))
def clean_text(value,maxlen,required=False):
 if not isinstance(value,str):raise ValueError('expected string')
 value=value.strip()
 if required and not value:raise ValueError('required field is empty')
 if len(value)>maxlen:raise ValueError(f'field exceeds {maxlen} characters')
 return value
def source_dict(c,source_id):
 r=c.execute('SELECT * FROM sources WHERE id=?',(source_id,)).fetchone();return dict(r) if r else None
def project_bundle(pid,private=False):
 with db() as c:
  p=c.execute('SELECT * FROM projects WHERE id=?',(pid,)).fetchone()
  if not p or (not private and p['status']!='published'):return None
  claim_sql='SELECT c.*,s.url AS source_url,s.publisher,s.retrieved_at,s.sha256 AS source_sha256 FROM claims c JOIN sources s ON s.id=c.source_id WHERE c.project_id=?'
  args=[pid]
  if not private:claim_sql+=' AND c.publication_state IN (?,?,?,?)';args+=sorted(PUBLIC_STATES)
  claim_sql+=' ORDER BY c.created_at'
  result={'project':dict(p),'claims':rows(c.execute(claim_sql,args)),'gaps':rows(c.execute('SELECT * FROM gaps WHERE project_id=? ORDER BY created_at',(pid,))),'responses':rows(c.execute('SELECT r.*,s.url AS source_url FROM responses r LEFT JOIN sources s ON s.id=r.source_id WHERE r.project_id=? ORDER BY r.created_at',(pid,)))}
  if private:result.update({'sources':rows(c.execute('SELECT * FROM sources WHERE project_id=? ORDER BY created_at',(pid,))),'documents':rows(c.execute('SELECT * FROM documents WHERE project_id=? ORDER BY created_at',(pid,)))})
  return result

class H(BaseHTTPRequestHandler):
 server_version='ProjectXRay/0.2';sys_version=''
 def setup(self):super().setup();self.request.settimeout(15);self.request_id=self.headers.get('X-Request-ID') if hasattr(self,'headers') else None
 def log_message(self,fmt,*args):print(json.dumps({'time':now(),'request_id':getattr(self,'request_id',''),'remote':self.client_address[0],'message':fmt%args},separators=(',',':')))
 def headers_common(self,code=200,ctype='application/json; charset=utf-8'):
  self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('X-Content-Type-Options','nosniff');self.send_header('X-Frame-Options','DENY');self.send_header('Referrer-Policy','no-referrer');self.send_header('Permissions-Policy','camera=(), microphone=(), geolocation=()');self.send_header('Content-Security-Policy',"default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; form-action 'self'; frame-ancestors 'none'");self.send_header('Cache-Control','no-store');self.send_header('X-Request-ID',self.request_id)
  if PUBLIC_BASE_URL.startswith('https://'):self.send_header('Strict-Transport-Security','max-age=31536000; includeSubDomains')
  self.end_headers()
 def out(self,obj,code=200):self.headers_common(code);self.wfile.write(json.dumps(obj,ensure_ascii=False,separators=(',',':')).encode())
 def text(self,value,code=200,ctype='text/plain; charset=utf-8'):self.headers_common(code,ctype);self.wfile.write(value.encode())
 def body(self):
  try:n=int(self.headers.get('Content-Length','0'))
  except ValueError:raise ValueError('invalid Content-Length')
  if n<=0:raise ValueError('JSON body required')
  if n>MAX:raise OverflowError('request too large')
  if self.headers.get('Content-Type','').split(';')[0].strip()!='application/json':raise TypeError('Content-Type must be application/json')
  try:return json.loads(self.rfile.read(n))
  except json.JSONDecodeError:raise ValueError('invalid JSON')
 def principal(self,roles=('admin',)):
  role,actor=auth(self.headers)
  if role not in roles:self.out({'error':'unauthorized'},401);return None
  return role,actor
 def limited(self):
  key=self.client_address[0];minute=int(time.time()//60);slot=RATE.setdefault((key,minute),0);RATE[(key,minute)]=slot+1
  for old in [k for k in RATE if k[1]<minute-1]:RATE.pop(old,None)
  return slot>=RATE_LIMIT
 def do_GET(self):
  self.request_id=self.headers.get('X-Request-ID') or uid('req');u=urlparse(self.path);path=u.path;query=parse_qs(u.query)
  if path=='/health':return self.out({'status':'ok','time':now(),'version':'0.2.0'})
  if path=='/ready':
   try:
    with db() as c:c.execute('SELECT 1').fetchone()
    return self.out({'status':'ready','time':now()})
   except Exception:return self.out({'status':'not_ready'},503)
  if path=='/api/projects':
   private=query.get('include_private')==['1'] and auth(self.headers)[0] in ('admin','reviewer')
   with db() as c:
    q='SELECT id,title,authority,location,summary,status,synthetic,created_at,updated_at FROM projects'
    if not private:q+=" WHERE status='published'"
    return self.out({'projects':rows(c.execute(q+' ORDER BY updated_at DESC'))})
  seg=[x for x in path.split('/') if x]
  if len(seg)>=3 and seg[:2]==['api','projects'] and valid_id(seg[2],'prj'):
   pid=seg[2];private=query.get('include_private')==['1'] and auth(self.headers)[0] in ('admin','reviewer');bundle=project_bundle(pid,private)
   if not bundle:return self.out({'error':'not found'},404)
   if len(seg)==3:return self.out(bundle)
   if len(seg)==4 and seg[3]=='report':
    p=bundle['project'];lines=[f"# Evidence report: {p['title']}",'',f"Generated: {now()}",f"Authority: {p['authority']}",'', '## Claims']
    for x in bundle['claims']:lines += [f"- [{x['claim_type']} / {x['publication_state']}] {x['text']}",f"  Source: {x['source_url']} (retrieved {x['retrieved_at']}; SHA-256 {x['source_sha256']})",f"  Anchor: {x['page_ref'] or x['passage']}"]
    lines += ['', '## Records not located']+[f"- {g['document_name']} — searched: {g['search_scope']} ({g['searched_at']})" for g in bundle['gaps']]
    return self.text('\n'.join(lines),ctype='text/markdown; charset=utf-8')
   if len(seg)==4 and seg[3]=='rti':
    p=bundle['project'];items='\n'.join(f"{i+1}. Certified electronic copy of {g['document_name']}." for i,g in enumerate(bundle['gaps'])) or '1. No document gaps have been selected.'
    return self.text(f"Draft RTI request — not legal advice\n\nTo: Public Information Officer, {p['authority']}\nSubject: Records concerning {p['title']}\n\nPlease provide:\n{items}\n\nPlease provide records electronically where available.\nGenerated {now()}")
   if len(seg)==4 and seg[3]=='audit':
    if not self.principal(('admin','reviewer')):return
    with db() as c:return self.out({'events':rows(c.execute("SELECT * FROM audit_events WHERE object_id=? OR detail LIKE ? ORDER BY id",(pid,'%project='+pid+'%')))})
  return self.serve_static(path)
 def serve_static(self,path):
  mapping={'/':'static/index.html','/index.html':'static/index.html','/app.js':'static/app.js','/styles.css':'static/styles.css'}
  rel=mapping.get(path)
  if not rel:return self.out({'error':'not found'},404)
  p=ROOT/rel;types={'.html':'text/html; charset=utf-8','.js':'application/javascript; charset=utf-8','.css':'text/css; charset=utf-8'}
  self.headers_common(200,types[p.suffix]);self.wfile.write(p.read_bytes())
 def do_POST(self):
  self.request_id=self.headers.get('X-Request-ID') or uid('req')
  if self.limited():return self.out({'error':'rate limit exceeded'},429)
  principal=self.principal(('admin','reviewer'))
  if not principal:return
  role,actor=principal;path=urlparse(self.path).path;seg=[x for x in path.split('/') if x]
  try:d=self.body()
  except OverflowError as e:return self.out({'error':str(e)},413)
  except (ValueError,TypeError) as e:return self.out({'error':str(e)},400)
  try:
   if path=='/api/projects':
    if role!='admin':return self.out({'error':'admin required'},403)
    title=clean_text(d.get('title',''),200,True);pid=uid('prj');t=now()
    with db() as c:c.execute('INSERT INTO projects VALUES(?,?,?,?,?,?,?,?,?)',(pid,title,clean_text(d.get('authority',''),200),clean_text(d.get('location',''),200),clean_text(d.get('summary',''),4000),d.get('status','research'),int(bool(d.get('synthetic',False))),t,t));audit(c,actor,'create','project',pid)
    return self.out({'id':pid},201)
   if len(seg)<4 or seg[:2]!=['api','projects'] or not valid_id(seg[2],'prj'):return self.out({'error':'not found'},404)
   pid=seg[2];kind=seg[3]
   with db() as c:
    if not c.execute('SELECT 1 FROM projects WHERE id=?',(pid,)).fetchone():return self.out({'error':'project not found'},404)
    if kind=='sources' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     url=clean_text(d.get('url',''),2000,True)
     if not url.startswith(('https://','http://')):return self.out({'error':'source URL must be http(s)'},400)
     sha=clean_text(d.get('sha256',''),64,True).lower()
     if not re.fullmatch(r'[a-f0-9]{64}',sha):return self.out({'error':'valid SHA-256 required'},400)
     oid=uid('src');c.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?,?,?)',(oid,pid,clean_text(d.get('publisher',''),200,True),url,clean_text(d.get('source_class','official'),50,True),clean_text(d.get('retrieved_at',now()),64,True),sha,clean_text(d.get('passage',''),4000),clean_text(d.get('page_ref',''),100),now()));audit(c,actor,'create','source',oid,'project='+pid);return self.out({'id':oid},201)
    if kind=='documents' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     sha=clean_text(d.get('sha256',''),64,True).lower();media=clean_text(d.get('media_type',''),100,True);allowed={'application/pdf','text/plain','text/csv','application/json','image/png','image/jpeg'}
     if not re.fullmatch(r'[a-f0-9]{64}',sha) or media not in allowed:return self.out({'error':'invalid hash or unsupported media type'},400)
     size=int(d.get('size_bytes',-1))
     if size<0 or size>MAX:return self.out({'error':'invalid or oversized document'},400)
     source_id=d.get('source_id') or None
     if source_id and not source_dict(c,source_id):return self.out({'error':'source not found'},400)
     oid=uid('doc');c.execute('INSERT INTO documents VALUES(?,?,?,?,?,?,?,?,?,?)',(oid,pid,source_id,clean_text(d.get('filename',''),255,True),media,size,sha,'quarantined','pending',now()));audit(c,actor,'create','document',oid,'project='+pid);return self.out({'id':oid,'storage_state':'quarantined'},201)
    if kind=='claims' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     if d.get('publication_state','candidate')!='candidate':return self.out({'error':'claims must begin as candidate'},400)
     ct=d.get('claim_type');source_id=d.get('source_id','');text=clean_text(d.get('text',''),8000,True);passage=clean_text(d.get('passage',''),4000);page_ref=clean_text(d.get('page_ref',''),100)
     if ct not in CLAIM_TYPES or not source_dict(c,source_id) or not (passage or page_ref):return self.out({'error':'valid type, source_id and passage/page_ref required'},400)
     oid=uid('clm');t=now();c.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?)',(oid,pid,source_id,ct,'candidate',text,passage,page_ref,actor,t,t));audit(c,actor,'create','claim',oid,'project='+pid);return self.out({'id':oid,'publication_state':'candidate'},201)
    if kind=='claims' and len(seg)==6 and valid_id(seg[4],'clm') and seg[5]=='reviews':
     if role!='reviewer':return self.out({'error':'independent reviewer token required'},403)
     cid=seg[4];decision=d.get('decision')
     if decision not in ('approve','reject'):return self.out({'error':'decision must be approve or reject'},400)
     if not c.execute('SELECT 1 FROM claims WHERE id=? AND project_id=?',(cid,pid)).fetchone():return self.out({'error':'claim not found'},404)
     oid=uid('rev');c.execute('INSERT INTO claim_reviews VALUES(?,?,?,?,?,?)',(oid,cid,actor,decision,clean_text(d.get('note',''),1000),now()));approvals=c.execute("SELECT COUNT(*) n FROM claim_reviews WHERE claim_id=? AND decision='approve'",(cid,)).fetchone()['n'];state='reviewed' if approvals>=2 else 'candidate';c.execute('UPDATE claims SET publication_state=?,updated_at=? WHERE id=?',(state,now(),cid));audit(c,actor,'review','claim',cid,decision);return self.out({'id':oid,'approvals':approvals,'publication_state':state},201)
    if kind=='claims' and len(seg)==6 and valid_id(seg[4],'clm') and seg[5]=='publish':
     if role!='admin':return self.out({'error':'admin required'},403)
     cid=seg[4];claim=c.execute('SELECT * FROM claims WHERE id=? AND project_id=?',(cid,pid)).fetchone();approvals=c.execute("SELECT COUNT(*) n FROM claim_reviews WHERE claim_id=? AND decision='approve'",(cid,)).fetchone()['n']
     if not claim or approvals<2:return self.out({'error':'two independent approvals required'},409)
     c.execute("UPDATE claims SET publication_state='published',updated_at=? WHERE id=?",(now(),cid));audit(c,actor,'publish','claim',cid,'project='+pid);return self.out({'id':cid,'publication_state':'published'})
    if kind=='gaps' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     oid=uid('gap');c.execute('INSERT INTO gaps VALUES(?,?,?,?,?,?,?)',(oid,pid,clean_text(d.get('document_name',''),300,True),clean_text(d.get('search_scope',''),2000,True),clean_text(d.get('searched_at',now()),64,True),d.get('status','not_located'),now()));audit(c,actor,'create','gap',oid,'project='+pid);return self.out({'id':oid},201)
    if kind=='responses' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     source_id=d.get('source_id') or None
     if source_id and not source_dict(c,source_id):return self.out({'error':'source not found'},400)
     oid=uid('rsp');c.execute('INSERT INTO responses VALUES(?,?,?,?,?,?)',(oid,pid,clean_text(d.get('responder',''),200,True),clean_text(d.get('text',''),8000,True),source_id,now()));audit(c,actor,'create','response',oid,'project='+pid);return self.out({'id':oid},201)
    if kind=='publish' and len(seg)==4:
     if role!='admin':return self.out({'error':'admin required'},403)
     unpublished=c.execute("SELECT COUNT(*) n FROM claims WHERE project_id=? AND publication_state NOT IN ('published','disputed','corrected','withdrawn')",(pid,)).fetchone()['n'];published=c.execute("SELECT COUNT(*) n FROM claims WHERE project_id=? AND publication_state='published'",(pid,)).fetchone()['n']
     if unpublished or not published:return self.out({'error':'project requires at least one published claim and no pending claims'},409)
     c.execute("UPDATE projects SET status='published',updated_at=? WHERE id=?",(now(),pid));audit(c,actor,'publish','project',pid);return self.out({'id':pid,'status':'published'})
   return self.out({'error':'not found'},404)
  except sqlite3.IntegrityError as e:return self.out({'error':'conflict','detail':str(e)},409)
  except (ValueError,TypeError) as e:return self.out({'error':str(e)},400)

if __name__=='__main__':
 init();print(json.dumps({'event':'startup','service':'project-xray','version':'0.2.0','port':PORT,'environment':ENV}));ThreadingHTTPServer(('0.0.0.0',PORT),H).serve_forever()
