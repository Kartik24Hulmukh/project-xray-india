import base64,time,unittest,uuid
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from app.scanner_attestation import canonical_payload,load_public_keys,verify_attestation
class TestScannerAttestation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.private=Ed25519PrivateKey.generate();pem=cls.private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode();cls.keys=load_public_keys(__import__('json').dumps({'scanner-key-1':pem}))
 def expected(self):return {'bucket':'quarantine','key':'objects/a','version_id':'v1','sha256':'a'*64,'size_bytes':128}
 def job(self):return {'id':'scn_'+'1'*16,'nonce':'nonce-12345678901234567890','scanner_identity':'scanner-1','policy_version':'beta-1'}
 def payload(self,**changes):
  now=int(time.time());value={'schema':'xray.scanner-attestation.v1','attestation_id':str(uuid.uuid4()),'scan_job_id':self.job()['id'],'challenge_nonce':self.job()['nonce'],'issued_at':now,'expires_at':now+120,'scanner_identity':'scanner-1','scanner_engine':'clamav','scanner_engine_version':'1.4.2','signature_database_version':'2026-07-18','policy_version':'beta-1','object':self.expected(),'started_at':now-2,'completed_at':now-1,'verdict':'clean','findings':[],'bytes_read':128,'key_id':'scanner-key-1'};value.update(changes);return value
 def sign(self,p):return base64.urlsafe_b64encode(self.private.sign(canonical_payload(p))).decode().rstrip('=')
 def test_valid_exact_attestation(self):
  p=self.payload();self.assertEqual(verify_attestation(p,self.sign(p),self.keys,self.expected(),self.job(),production=True),'clean')
 def test_tamper_replay_context_and_short_read_fail(self):
  for change in ({'bytes_read':127},{'challenge_nonce':'other-nonce-1234567890'},{'scanner_identity':'other'},{'policy_version':'old'},{'object':{**self.expected(),'version_id':'v2'}},{'expires_at':int(time.time())-1}):
   p=self.payload(**change)
   with self.assertRaises(PermissionError):verify_attestation(p,self.sign(p),self.keys,self.expected(),self.job(),production=True)
 def test_signature_tampering_and_test_engine_fail(self):
  p=self.payload();sig=self.sign(p);p['verdict']='infected'
  with self.assertRaises(PermissionError):verify_attestation(p,sig,self.keys,self.expected(),self.job(),production=True)
  p=self.payload(scanner_engine='synthetic')
  with self.assertRaises(PermissionError):verify_attestation(p,self.sign(p),self.keys,self.expected(),self.job(),production=True)
 def test_unknown_fields_and_key_type_fail(self):
  p=self.payload(extra='private')
  with self.assertRaises(PermissionError):verify_attestation(p,self.sign(p),self.keys,self.expected(),self.job())
  with self.assertRaises(ValueError):load_public_keys('{}')
if __name__=='__main__':unittest.main()
