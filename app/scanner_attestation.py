"""Integrity-bound Ed25519 scanner attestations.

A valid signature proves who attested to scanning an exact object version; it
does not prove that an engine detects all malware.
"""
from __future__ import annotations
import base64,json,time,uuid
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
SCHEMA='xray.scanner-attestation.v1';VERDICTS={'clean','infected','error','unsupported','timeout'}
def canonical_payload(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def b64url_decode(value):return base64.urlsafe_b64decode(value+'='*((4-len(value)%4)%4))
def load_public_keys(raw):
 try:value=json.loads(raw)
 except Exception as exc:raise ValueError('invalid scanner public-key configuration') from exc
 if not isinstance(value,dict) or not value:raise ValueError('scanner public keys must be a non-empty object')
 result={}
 for key_id,pem in value.items():
  if not isinstance(key_id,str) or not key_id or not isinstance(pem,str):raise ValueError('invalid scanner key entry')
  try:key=serialization.load_pem_public_key(pem.encode())
  except Exception as exc:raise ValueError('invalid scanner public key') from exc
  if not isinstance(key,Ed25519PublicKey):raise ValueError('scanner key must be Ed25519')
  result[key_id]=key
 return result
def verify_attestation(payload,signature,keys,expected_object,expected_job,now_epoch=None,production=False):
 if not isinstance(payload,dict) or set(payload)!={'schema','attestation_id','scan_job_id','challenge_nonce','issued_at','expires_at','scanner_identity','scanner_engine','scanner_engine_version','signature_database_version','policy_version','object','started_at','completed_at','verdict','findings','bytes_read','key_id'}:raise PermissionError('invalid scanner attestation fields')
 if payload['schema']!=SCHEMA or payload['verdict'] not in VERDICTS:raise PermissionError('invalid scanner attestation')
 try:uuid.UUID(str(payload['attestation_id']))
 except Exception as exc:raise PermissionError('invalid attestation id') from exc
 if payload['scan_job_id']!=expected_job['id'] or payload['challenge_nonce']!=expected_job['nonce']:raise PermissionError('scanner challenge mismatch')
 if payload['object']!=expected_object:raise PermissionError('scanner object binding mismatch')
 if payload['bytes_read']!=expected_object['size_bytes']:raise PermissionError('incomplete scanner read')
 now=int(time.time()) if now_epoch is None else int(now_epoch);issued=int(payload['issued_at']);expires=int(payload['expires_at'])
 if issued>now+5 or expires<=now or expires<=issued or expires-issued>300:raise PermissionError('scanner attestation expired or invalid')
 if str(payload['scanner_identity'])!=str(expected_job['scanner_identity']) or str(payload['policy_version'])!=str(expected_job['policy_version']):raise PermissionError('scanner identity or policy mismatch')
 if production and str(payload['scanner_engine']).lower() in {'test','synthetic','fixture','none'}:raise PermissionError('test scanner forbidden in production')
 key=keys.get(payload['key_id'])
 if key is None:raise PermissionError('unknown scanner key')
 try:key.verify(b64url_decode(signature),canonical_payload(payload))
 except Exception as exc:raise PermissionError('invalid scanner signature') from exc
 return payload['verdict']
