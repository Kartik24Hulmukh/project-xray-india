import json,time,unittest
import jwt
from email.message import Message
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from app.alb_gateway import ALBIdentityVerifier,GatewayConfigurationError,duplicate_identity_headers,load_role_bindings
from app.gateway import stable_principal
SIGNER='arn:aws:elasticloadbalancing:ap-south-1:111122223333:loadbalancer/app/synthetic/abc';CLIENT='synthetic-client';ISSUER='https://cognito-idp.ap-south-1.amazonaws.com/synthetic-pool'
class TestALBGateway(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.private=ec.generate_private_key(ec.SECP256R1());cls.public=cls.private.public_key().public_bytes(serialization.Encoding.PEM,serialization.PublicFormat.SubjectPublicKeyInfo).decode()
 def verifier(self):return ALBIdentityVerifier(region='ap-south-1',expected_signer=SIGNER,expected_client=CLIENT,expected_issuer=ISSUER,key_loader=lambda kid:self.public)
 def token(self,**overrides):
  h={'kid':'synthetic-key','signer':SIGNER,'client':CLIENT,'iss':ISSUER,'exp':int(time.time())+60};h.update(overrides)
  return jwt.encode({'sub':'reviewer-a'},self.private,algorithm='ES256',headers=h)
 def test_valid_signature_and_context(self):self.assertEqual(self.verifier().verify(self.token(),'reviewer-a'),(ISSUER,'reviewer-a'))
 def test_wrong_context_identity_expiry_and_algorithm_fail(self):
  for change,identity in [({'signer':'bad'},'reviewer-a'),({'client':'bad'},'reviewer-a'),({'iss':'bad'},'reviewer-a'),({},'other'),({'exp':int(time.time())-1},'reviewer-a')]:
   with self.assertRaises(PermissionError):self.verifier().verify(self.token(**change),identity)
  bad=jwt.encode({'sub':'reviewer-a'},'secret',algorithm='HS256',headers={'kid':'x','signer':SIGNER,'client':CLIENT,'iss':ISSUER,'exp':int(time.time())+60})
  with self.assertRaises(PermissionError):self.verifier().verify(bad,'reviewer-a')
 def test_signature_failure(self):
  other=ec.generate_private_key(ec.SECP256R1());bad=jwt.encode({'sub':'reviewer-a'},other,algorithm='ES256',headers={'kid':'x','signer':SIGNER,'client':CLIENT,'iss':ISSUER,'exp':int(time.time())+60})
  with self.assertRaises(PermissionError):self.verifier().verify(bad,'reviewer-a')
 def test_duplicate_identity_headers_fail(self):
  h=Message();h['x-amzn-oidc-data']='one';h['x-amzn-oidc-data']='two';h['x-amzn-oidc-identity']='subject';self.assertTrue(duplicate_identity_headers(h))
  h=Message();h['x-amzn-oidc-data']='one';h['x-amzn-oidc-identity']='subject';self.assertFalse(duplicate_identity_headers(h))
 def test_role_binding_configuration(self):
  p=stable_principal(ISSUER,'reviewer-a');self.assertEqual(load_role_bindings(json.dumps({p:'reviewer'})),{p:'reviewer'})
  for value in ('','[]','{"bad":"reviewer"}',json.dumps({p:'root'})):
   with self.assertRaises(GatewayConfigurationError):load_role_bindings(value)
if __name__=='__main__':unittest.main()
