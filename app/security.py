import hashlib,hmac,time
from datetime import datetime,timezone

def token_hash(token,pepper):return hmac.new(pepper.encode(),token.encode(),hashlib.sha256).hexdigest()
def iso_now():return datetime.now(timezone.utc).isoformat()
def proxy_signature(subject,roles,mfa,timestamp,secret):
 message='|'.join((subject,roles,mfa,timestamp));return hmac.new(secret.encode(),message.encode(),hashlib.sha256).hexdigest()
def verify_proxy(headers,secret,max_age=90):
 subject=headers.get('X-Auth-Subject','').strip();roles=headers.get('X-Auth-Roles','').strip();mfa=headers.get('X-Auth-MFA','').strip().lower();stamp=headers.get('X-Auth-Timestamp','').strip();signature=headers.get('X-Auth-Signature','').strip()
 if not all((subject,roles,stamp,signature)) or mfa!='true':return None
 try:
  if abs(time.time()-int(stamp))>max_age:return None
 except ValueError:return None
 expected=proxy_signature(subject,roles,mfa,stamp,secret)
 if not hmac.compare_digest(signature,expected):return None
 allowed=[r.strip() for r in roles.split(',') if r.strip() in {'admin','reviewer','scanner'}]
 return (allowed[0],subject) if allowed else None
