PRAGMA foreign_keys=ON;
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS projects(
 id TEXT PRIMARY KEY,title TEXT NOT NULL,authority TEXT NOT NULL DEFAULT '',location TEXT NOT NULL DEFAULT '',summary TEXT NOT NULL DEFAULT '',status TEXT NOT NULL DEFAULT 'research' CHECK(status IN ('research','review','published','withdrawn')),synthetic INTEGER NOT NULL DEFAULT 0 CHECK(synthetic IN (0,1)),created_at TEXT NOT NULL,updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sources(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,publisher TEXT NOT NULL,url TEXT NOT NULL,source_class TEXT NOT NULL,retrieved_at TEXT NOT NULL,sha256 TEXT NOT NULL,passage TEXT NOT NULL DEFAULT '',page_ref TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,UNIQUE(project_id,url,sha256),FOREIGN KEY(project_id) REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS documents(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,source_id TEXT,filename TEXT NOT NULL,media_type TEXT NOT NULL,size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),sha256 TEXT NOT NULL,storage_state TEXT NOT NULL DEFAULT 'metadata_only' CHECK(storage_state IN ('metadata_only','quarantined','clean','rejected')),scan_result TEXT NOT NULL DEFAULT 'not_run',created_at TEXT NOT NULL,UNIQUE(project_id,sha256),FOREIGN KEY(project_id) REFERENCES projects(id),FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS claims(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,source_id TEXT NOT NULL,claim_type TEXT NOT NULL CHECK(claim_type IN ('verified_fact','reported_allegation','official_claim','expert_assessment','data_inconsistency','audit_finding','court_finding')),publication_state TEXT NOT NULL DEFAULT 'candidate' CHECK(publication_state IN ('candidate','reviewed','published','disputed','corrected','withdrawn')),text TEXT NOT NULL,passage TEXT NOT NULL DEFAULT '',page_ref TEXT NOT NULL DEFAULT '',created_by TEXT NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,FOREIGN KEY(project_id) REFERENCES projects(id),FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS claim_reviews(
 id TEXT PRIMARY KEY,claim_id TEXT NOT NULL,reviewer TEXT NOT NULL,decision TEXT NOT NULL CHECK(decision IN ('approve','reject')),note TEXT NOT NULL DEFAULT '',created_at TEXT NOT NULL,UNIQUE(claim_id,reviewer),FOREIGN KEY(claim_id) REFERENCES claims(id)
);
CREATE TABLE IF NOT EXISTS claim_revisions(
 id TEXT PRIMARY KEY,claim_id TEXT NOT NULL,previous_text TEXT NOT NULL,new_text TEXT NOT NULL,reason TEXT NOT NULL,actor TEXT NOT NULL,created_at TEXT NOT NULL,FOREIGN KEY(claim_id) REFERENCES claims(id)
);
CREATE TABLE IF NOT EXISTS gaps(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,document_name TEXT NOT NULL,search_scope TEXT NOT NULL,searched_at TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'not_located' CHECK(status IN ('not_located','requested','received','not_held')),created_at TEXT NOT NULL,FOREIGN KEY(project_id) REFERENCES projects(id)
);
CREATE TABLE IF NOT EXISTS responses(
 id TEXT PRIMARY KEY,project_id TEXT NOT NULL,responder TEXT NOT NULL,text TEXT NOT NULL,source_id TEXT,created_at TEXT NOT NULL,FOREIGN KEY(project_id) REFERENCES projects(id),FOREIGN KEY(source_id) REFERENCES sources(id)
);
CREATE TABLE IF NOT EXISTS audit_events(
 id INTEGER PRIMARY KEY AUTOINCREMENT,event_id TEXT NOT NULL UNIQUE,actor TEXT NOT NULL,action TEXT NOT NULL,object_type TEXT NOT NULL,object_id TEXT NOT NULL,detail TEXT NOT NULL DEFAULT '',previous_hash TEXT NOT NULL DEFAULT '',event_hash TEXT NOT NULL UNIQUE,created_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'audit events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'audit events are immutable'); END;
CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status,updated_at);
CREATE INDEX IF NOT EXISTS idx_sources_project ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id);
CREATE INDEX IF NOT EXISTS idx_claims_project_state ON claims(project_id,publication_state);
CREATE INDEX IF NOT EXISTS idx_claim_reviews_claim ON claim_reviews(claim_id);
CREATE INDEX IF NOT EXISTS idx_gaps_project ON gaps(project_id);
CREATE INDEX IF NOT EXISTS idx_responses_project ON responses(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_events(object_type,object_id);
