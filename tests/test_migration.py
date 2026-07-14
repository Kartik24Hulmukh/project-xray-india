import sqlite3,tempfile,unittest
from pathlib import Path
from scripts.migrate_legacy import migrate
ROOT=Path(__file__).resolve().parents[1]
class TestLegacyMigration(unittest.TestCase):
 def test_legacy_claim_is_preserved_but_demoted(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'legacy.db';c=sqlite3.connect(p);c.executescript('''
CREATE TABLE projects(id TEXT PRIMARY KEY,title TEXT,authority TEXT,location TEXT,summary TEXT,status TEXT,synthetic INTEGER,created_at TEXT,updated_at TEXT);
CREATE TABLE sources(id TEXT,project_id TEXT,publisher TEXT,url TEXT,source_class TEXT,retrieved_at TEXT,sha256 TEXT);
CREATE TABLE claims(id TEXT PRIMARY KEY,project_id TEXT,claim_type TEXT,publication_state TEXT,text TEXT,source_url TEXT,publisher TEXT,passage TEXT,page_ref TEXT,reviewer TEXT,reviewed_at TEXT,created_at TEXT);
CREATE TABLE gaps(id TEXT,project_id TEXT,document_name TEXT,search_scope TEXT,searched_at TEXT,status TEXT,created_at TEXT);
CREATE TABLE responses(id TEXT,project_id TEXT,responder TEXT,text TEXT,source_url TEXT,created_at TEXT);
''');c.execute("INSERT INTO projects VALUES('prj_aaaaaaaaaaaaaaaa','Legacy','','','','published',1,'t','t')");c.execute("INSERT INTO claims VALUES('clm_aaaaaaaaaaaaaaaa','prj_aaaaaaaaaaaaaaaa','official_claim','published','Legacy text','https://example.invalid/legacy','Publisher','Passage','','reviewer','t','t')");c.commit();c.close()
   result=migrate(p);self.assertEqual(result['status'],'migrated');self.assertTrue(result['claims_demoted_to_candidate']);self.assertTrue(Path(str(p)+'.pre-v2.bak').exists())
   c=sqlite3.connect(p);self.assertEqual(c.execute('SELECT publication_state FROM claims').fetchone()[0],'candidate');self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],3);c.close()
if __name__=='__main__':unittest.main()
