import hashlib,hmac,json,os
from datetime import datetime,timezone
from pathlib import Path

def file_sha256(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
 return h.hexdigest()
def canonical(payload):return json.dumps(payload,sort_keys=True,separators=(',',':')).encode()
def sign(payload,key):return hmac.new(key.encode(),canonical(payload),hashlib.sha256).hexdigest()
def create(path,artifact,key,extra=None):
 artifact=Path(artifact);payload={'artifact':artifact.name,'sha256':file_sha256(artifact),'size_bytes':artifact.stat().st_size,'created_at':datetime.now(timezone.utc).isoformat(),**(extra or {})};doc={'payload':payload,'signature':sign(payload,key)};Path(path).write_text(json.dumps(doc,indent=2,sort_keys=True)+'\n');os.chmod(path,0o600);return doc
def verify(path,artifact,key):
 doc=json.loads(Path(path).read_text());payload=doc.get('payload',{});expected=sign(payload,key)
 if not hmac.compare_digest(str(doc.get('signature','')),expected):raise RuntimeError('manifest signature invalid')
 artifact=Path(artifact)
 if payload.get('artifact')!=artifact.name or payload.get('sha256')!=file_sha256(artifact) or payload.get('size_bytes')!=artifact.stat().st_size:raise RuntimeError('artifact does not match authenticated manifest')
 return doc
