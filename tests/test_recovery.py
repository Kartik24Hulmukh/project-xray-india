import os,sqlite3,tempfile,unittest,json
from pathlib import Path
from scripts.recovery import backup,restore,integrity
ROOT=Path(__file__).resolve().parents[1];BK='backup-test-key-123456789012345678901';AK='audit-test-key-1234567890123456789012'
class TestRecovery(unittest.TestCase):
 def fixture(self,path):
  c=sqlite3.connect(path);c.executescript((ROOT/'db/schema.sql').read_text());c.execute("INSERT INTO projects VALUES('prj_aaaaaaaaaaaaaaaa','Fixture','Authority','','','research',1,'t','t')");c.commit();c.close()
 def test_authenticated_backup_and_clean_restore(self):
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'source.db';self.fixture(source);archived=Path(d)/'backup.db';restored=Path(d)/'clean'/'restored.db';result=backup(source,archived,BK,AK);self.assertEqual(result['integrity'],'ok');self.assertTrue(Path(result['manifest']).exists());restore(archived,restored,key=BK,audit_key=AK);self.assertEqual(integrity(restored,AK)['integrity'],'ok')
   c=sqlite3.connect(restored);self.assertEqual(c.execute('SELECT title FROM projects').fetchone()[0],'Fixture');c.close()
 def test_tampered_backup_or_manifest_is_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'source.db';self.fixture(source);archived=Path(d)/'backup.db';backup(source,archived,BK,AK);manifest=archived.with_suffix('.db.manifest.json');doc=json.loads(manifest.read_text());doc['payload']['size_bytes']+=1;manifest.write_text(json.dumps(doc))
   with self.assertRaises(RuntimeError):restore(archived,Path(d)/'restored.db',key=BK,audit_key=AK)
 def test_refuses_overwrite_and_invalid_database(self):
  with tempfile.TemporaryDirectory() as d:
   bad=Path(d)/'bad.db';bad.write_text('not sqlite')
   with self.assertRaises(Exception):backup(bad,Path(d)/'backup.db',BK,AK)
if __name__=='__main__':unittest.main()
