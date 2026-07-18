import json,tempfile,unittest
from pathlib import Path
from scripts.validate_aws_receipts import CATEGORIES,validate
SHA='a'*40;DIGEST='sha256:'+'b'*64
class TestAWSReceipts(unittest.TestCase):
 def receipt(self,category,**changes):
  value={'category':category,'status':'passed','environment':'staging','account_id':'111122223333','region':'ap-south-1','git_sha':SHA,'image_digest':DIGEST,'observed_at':'2026-07-18T10:00:00+00:00','operator':'synthetic-operator','evidence':{'synthetic':True}};value.update(changes);return value
 def write_all(self,root,**changes):
  for category in CATEGORIES:(root/f'{category}.json').write_text(json.dumps(self.receipt(category,**changes)))
 def test_complete_consistent_set_passes(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.write_all(root);result=validate(root,'staging');self.assertEqual(result['status'],'passed');self.assertEqual(result['receipt_count'],8)
 def test_missing_failed_or_mismatched_receipt_blocks(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.write_all(root);(root/'load.json').unlink();self.assertEqual(validate(root,'staging')['status'],'blocked')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.write_all(root);(root/'storage.json').write_text(json.dumps(self.receipt('storage',status='failed')));self.assertEqual(validate(root,'staging')['status'],'blocked')
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.write_all(root);(root/'deployment.json').write_text(json.dumps(self.receipt('deployment',git_sha='c'*40)));self.assertIn('receipts disagree on git_sha',validate(root,'staging')['errors'])
 def test_extra_fields_and_synthetic_production_are_not_silently_accepted(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);self.write_all(root);value=self.receipt('identity',unexpected='secret');(root/'identity.json').write_text(json.dumps(value));self.assertEqual(validate(root,'staging')['status'],'blocked')
if __name__=='__main__':unittest.main()
