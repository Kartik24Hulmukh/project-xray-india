-- PostgreSQL schema for Project X-Ray India
-- Compatible with the SQLite schema but using PostgreSQL syntax

CREATE TABLE IF NOT EXISTS schema_version (
    id INTEGER PRIMARY KEY DEFAULT 1,
    value INTEGER NOT NULL DEFAULT 0,
    CONSTRAINT single_row CHECK (id = 1)
);

INSERT INTO schema_version (id, value) VALUES (1, 0)
    ON CONFLICT (id) DO NOTHING;

CREATE TABLE IF NOT EXISTS projects(
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authority TEXT NOT NULL DEFAULT '',
    location TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'research' CHECK(status IN ('research','review','published','withdrawn')),
    synthetic INTEGER NOT NULL DEFAULT 0 CHECK(synthetic IN (0,1)),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sources(
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    publisher TEXT NOT NULL,
    url TEXT NOT NULL,
    source_class TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    passage TEXT NOT NULL DEFAULT '',
    page_ref TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(project_id,url,sha256),
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS documents(
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_id TEXT,
    filename TEXT NOT NULL,
    media_type TEXT NOT NULL,
    size_bytes INTEGER NOT NULL CHECK(size_bytes>=0),
    sha256 TEXT NOT NULL,
    storage_state TEXT NOT NULL DEFAULT 'metadata_only' CHECK(storage_state IN ('metadata_only','quarantined','clean','rejected')),
    scan_result TEXT NOT NULL DEFAULT 'not_run',
    storage_uri TEXT NOT NULL DEFAULT '',
    scanned_at TEXT NOT NULL DEFAULT '',
    scanned_by TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(project_id,sha256),
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS claims(
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    source_id TEXT NOT NULL,
    claim_type TEXT NOT NULL CHECK(claim_type IN ('verified_fact','reported_allegation','official_claim','expert_assessment','data_inconsistency','audit_finding','court_finding')),
    publication_state TEXT NOT NULL DEFAULT 'candidate' CHECK(publication_state IN ('candidate','reviewed','published','disputed','corrected','withdrawn')),
    text TEXT NOT NULL,
    passage TEXT NOT NULL DEFAULT '',
    page_ref TEXT NOT NULL DEFAULT '',
    created_by TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK(version>0),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS claim_reviews(
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    claim_version INTEGER NOT NULL,
    reviewer TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('approve','reject')),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    UNIQUE(claim_id,claim_version,reviewer),
    FOREIGN KEY(claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS claim_revisions(
    id TEXT PRIMARY KEY,
    claim_id TEXT NOT NULL,
    previous_version INTEGER NOT NULL,
    new_version INTEGER NOT NULL,
    previous_text TEXT NOT NULL,
    new_text TEXT NOT NULL,
    reason TEXT NOT NULL,
    actor TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(claim_id,new_version),
    FOREIGN KEY(claim_id) REFERENCES claims(id)
);

CREATE TABLE IF NOT EXISTS gaps(
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    document_name TEXT NOT NULL,
    search_scope TEXT NOT NULL,
    searched_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'not_located' CHECK(status IN ('not_located','requested','received','not_held')),
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id)
);

CREATE TABLE IF NOT EXISTS responses(
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    responder TEXT NOT NULL,
    text TEXT NOT NULL,
    source_id TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(id),
    FOREIGN KEY(source_id) REFERENCES sources(id)
);

CREATE TABLE IF NOT EXISTS auth_tokens(
    id TEXT PRIMARY KEY,
    principal TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin','reviewer','scanner')),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    revoked_at TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    rotated_from TEXT,
    FOREIGN KEY(rotated_from) REFERENCES auth_tokens(id)
);

CREATE TABLE IF NOT EXISTS audit_events(
    id SERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    previous_hash TEXT NOT NULL DEFAULT '',
    event_hash TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_checkpoints(
    id SERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    event_count INTEGER NOT NULL,
    head_hash TEXT NOT NULL,
    signature TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES audit_events(event_id)
);

CREATE TABLE IF NOT EXISTS idempotency_keys(
    principal TEXT NOT NULL,
    key TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('processing','completed')),
    response_code INTEGER,
    response_body TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT NOT NULL DEFAULT '',
    PRIMARY KEY(principal,key)
);

-- Audit immutability triggers (PostgreSQL uses functions + triggers)
CREATE OR REPLACE FUNCTION audit_no_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION audit_no_delete() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit events are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION checkpoint_no_update() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit checkpoints are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION checkpoint_no_delete() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit checkpoints are immutable';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_audit_no_update ON audit_events;
CREATE TRIGGER trg_audit_no_update BEFORE UPDATE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_no_update();

DROP TRIGGER IF EXISTS trg_audit_no_delete ON audit_events;
CREATE TRIGGER trg_audit_no_delete BEFORE DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION audit_no_delete();

DROP TRIGGER IF EXISTS trg_checkpoint_no_update ON audit_checkpoints;
CREATE TRIGGER trg_checkpoint_no_update BEFORE UPDATE ON audit_checkpoints
    FOR EACH ROW EXECUTE FUNCTION checkpoint_no_update();

DROP TRIGGER IF EXISTS trg_checkpoint_no_delete ON audit_checkpoints;
CREATE TRIGGER trg_checkpoint_no_delete BEFORE DELETE ON audit_checkpoints
    FOR EACH ROW EXECUTE FUNCTION checkpoint_no_delete();

CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status,updated_at);
CREATE INDEX IF NOT EXISTS idx_sources_project ON sources(project_id);
CREATE INDEX IF NOT EXISTS idx_documents_project ON documents(project_id,storage_state);
CREATE INDEX IF NOT EXISTS idx_claims_project_state ON claims(project_id,publication_state);
CREATE INDEX IF NOT EXISTS idx_claim_reviews_claim_version ON claim_reviews(claim_id,claim_version);
CREATE INDEX IF NOT EXISTS idx_gaps_project ON gaps(project_id);
CREATE INDEX IF NOT EXISTS idx_responses_project ON responses(project_id);
CREATE INDEX IF NOT EXISTS idx_audit_object ON audit_events(object_type,object_id);
CREATE INDEX IF NOT EXISTS idx_auth_active ON auth_tokens(token_hash,revoked_at,expires_at);

-- Set schema version to 3
UPDATE schema_version SET value = 3 WHERE id = 1;
