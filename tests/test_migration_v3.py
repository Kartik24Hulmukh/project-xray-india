import sqlite3,tempfile,unittest
from pathlib import Path
from scripts.migrate_v2_to_v3 import migrate
class TestV3Migration(unittest.TestCase):
 def test_atomic_v2_migration_demotes_publication_and_signs_backup(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'v2.db';c=sqlite3.connect(p);c.executescript('''
PRAGMA user_version=2;
CREATE TABLE projects(id TEXT PRIMARY KEY,title TEXT,authority TEXT,location TEXT,summary TEXT,status TEXT,synthetic INTEGER,created_at TEXT,updated_at TEXT);
CREATE TABLE sources(id TEXT PRIMARY KEY,project_id TEXT,publisher TEXT,url TEXT,source_class TEXT,retrieved_at TEXT,sha256 TEXT,passage TEXT,page_ref TEXT,created_at TEXT);
CREATE TABLE documents(id TEXT PRIMARY KEY,project_id TEXT,source_id TEXT,filename TEXT,media_type TEXT,size_bytes INTEGER,sha256 TEXT,storage_state TEXT,scan_result TEXT,created_at TEXT);
CREATE TABLE claims(id TEXT PRIMARY KEY,project_id TEXT,source_id TEXT,claim_type TEXT,publication_state TEXT,text TEXT,passage TEXT,page_ref TEXT,created_by TEXT,created_at TEXT,updated_at TEXT);
CREATE TABLE claim_reviews(id TEXT PRIMARY KEY,claim_id TEXT,reviewer TEXT,decision TEXT,note TEXT,created_at TEXT);
CREATE TABLE claim_revisions(id TEXT PRIMARY KEY,claim_id TEXT,previous_text TEXT,new_text TEXT,reason TEXT,actor TEXT,created_at TEXT);
CREATE TABLE gaps(id TEXT,project_id TEXT,document_name TEXT,search_scope TEXT,searched_at TEXT,status TEXT,created_at TEXT);
CREATE TABLE responses(id TEXT,project_id TEXT,responder TEXT,text TEXT,source_id TEXT,created_at TEXT);
CREATE TABLE audit_events(id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT UNIQUE,actor TEXT,action TEXT,object_type TEXT,object_id TEXT,detail TEXT,previous_hash TEXT,event_hash TEXT UNIQUE,created_at TEXT);
''');c.execute("INSERT INTO projects VALUES('prj_aaaaaaaaaaaaaaaa','P','','','','published',1,'t','t')");c.execute("INSERT INTO sources VALUES('src_aaaaaaaaaaaaaaaa','prj_aaaaaaaaaaaaaaaa','Pub','https://example.invalid','official','t',?,'anchor','','t')",('a'*64,));c.execute("INSERT INTO claims VALUES('clm_aaaaaaaaaaaaaaaa','prj_aaaaaaaaaaaaaaaa','src_aaaaaaaaaaaaaaaa','official_claim','published','text','anchor','','admin','t','t')");c.commit();c.close()
   result=migrate(p,'b'*40,'a'*40);self.assertEqual(result['status'],'migrated');self.assertTrue(Path(result['manifest']).exists())
   c=sqlite3.connect(p);self.assertEqual(c.execute('PRAGMA user_version').fetchone()[0],3);self.assertEqual(c.execute('SELECT publication_state FROM claims').fetchone()[0],'candidate');self.assertEqual(c.execute('SELECT status FROM projects').fetchone()[0],'research');c.close()
if __name__=='__main__':unittest.main()
