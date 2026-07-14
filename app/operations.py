import hashlib,hmac,json,os,urllib.request,uuid
from datetime import datetime,timezone

def send_alert(event,url=None,secret=None,timeout=5):
 url=url or os.getenv('MONITORING_WEBHOOK_URL','');secret=secret or os.getenv('MONITORING_WEBHOOK_SECRET','')
 if not url or not secret:raise RuntimeError('monitoring webhook is not configured')
 payload={'event_id':'ops_'+uuid.uuid4().hex[:16],'service':'project-xray','created_at':datetime.now(timezone.utc).isoformat(),**event};body=json.dumps(payload,sort_keys=True,separators=(',',':')).encode();signature=hmac.new(secret.encode(),body,hashlib.sha256).hexdigest();req=urllib.request.Request(url,data=body,headers={'Content-Type':'application/json','X-Project-XRay-Signature':'sha256='+signature},method='POST')
 with urllib.request.urlopen(req,timeout=timeout) as response:
  if response.status<200 or response.status>=300:raise RuntimeError(f'alert webhook returned {response.status}')
 return payload
