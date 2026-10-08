CREATE EXTENSION IF NOT EXISTS vector;
CREATE SCHEMA intelligence;
CREATE SCHEMA observation_workspace;
CREATE SCHEMA quality_control;
CREATE SCHEMA knowledge;

CREATE TABLE intelligence.texts (hash TEXT PRIMARY KEY, text TEXT NOT NULL);
CREATE TABLE intelligence.identities (id TEXT PRIMARY KEY, metadata TEXT NOT NULL CHECK (metadata::jsonb IS NOT NULL));
CREATE TABLE intelligence.observations (
    id TEXT PRIMARY KEY, hash TEXT NOT NULL REFERENCES intelligence.texts(hash),
    dataset TEXT, grain TEXT, inspection_id TEXT, company TEXT, site TEXT, year INTEGER,
    product TEXT, inspection_type TEXT, frequency INTEGER, source TEXT NOT NULL CHECK (source::jsonb IS NOT NULL));
CREATE INDEX obs_hash ON intelligence.observations(hash);
CREATE INDEX obs_company ON intelligence.observations(company);
CREATE INDEX obs_site ON intelligence.observations(site);
CREATE INDEX obs_dataset ON intelligence.observations(dataset);
CREATE TABLE intelligence.origins (observation_id TEXT REFERENCES intelligence.observations(id), origin TEXT, PRIMARY KEY(observation_id, origin));
CREATE TABLE intelligence.conflicts (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, identity TEXT, existing TEXT, incoming TEXT, source TEXT);
CREATE TABLE intelligence.corpus (key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE intelligence.cache (key TEXT PRIMARY KEY, hash TEXT NOT NULL REFERENCES intelligence.texts(hash), payload TEXT CHECK(payload::jsonb IS NOT NULL));
CREATE TABLE intelligence.runs (id TEXT PRIMARY KEY, payload TEXT CHECK(payload::jsonb IS NOT NULL), storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE);
CREATE TABLE intelligence.assignments (run_id TEXT REFERENCES intelligence.runs(id), hash TEXT REFERENCES intelligence.texts(hash), cache_key TEXT REFERENCES intelligence.cache(key), group_id TEXT, similarity DOUBLE PRECISION, method TEXT, PRIMARY KEY(run_id,hash));
CREATE TABLE intelligence.members (run_id TEXT REFERENCES intelligence.runs(id), observation_id TEXT REFERENCES intelligence.observations(id), PRIMARY KEY(run_id,observation_id));
CREATE TABLE intelligence.embeddings (hash TEXT REFERENCES intelligence.texts(hash), model TEXT, version TEXT, payload TEXT, PRIMARY KEY(hash,model,version));
CREATE TABLE intelligence.quarantine (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, reason TEXT NOT NULL, payload TEXT NOT NULL);
CREATE INDEX assignment_group ON intelligence.assignments(run_id,group_id);
CREATE TABLE intelligence.website_index_runs (run_id TEXT PRIMARY KEY REFERENCES intelligence.runs(id));
CREATE TABLE intelligence.website_index (
    run_id TEXT REFERENCES intelligence.runs(id), id TEXT REFERENCES intelligence.observations(id), hash TEXT,
    inspection_id TEXT, dataset TEXT, grain TEXT, company TEXT, site TEXT, year INTEGER,
    group_id TEXT, theme TEXT, severity TEXT, severity_rank INTEGER, PRIMARY KEY(run_id,id));
CREATE INDEX website_severity ON intelligence.website_index(run_id,dataset,grain,severity_rank,id);
CREATE INDEX website_year ON intelligence.website_index(run_id,dataset,grain,year,id);
CREATE INDEX website_group ON intelligence.website_index(run_id,group_id,dataset,inspection_id);
CREATE TABLE intelligence.website_reviews (
    run_id TEXT NOT NULL REFERENCES intelligence.runs(id), observation_id TEXT NOT NULL REFERENCES intelligence.observations(id),
    revision INTEGER NOT NULL, payload TEXT NOT NULL CHECK(payload::jsonb IS NOT NULL),
    storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE, PRIMARY KEY(run_id,observation_id,revision));
CREATE TABLE intelligence.retrieval_summaries (run_id TEXT REFERENCES intelligence.runs(id), dataset TEXT, payload TEXT, PRIMARY KEY(run_id,dataset));

CREATE TABLE observation_workspace.runs (id TEXT PRIMARY KEY, payload TEXT CHECK(payload::jsonb IS NOT NULL), storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE);
CREATE TABLE observation_workspace.tags (run_id TEXT REFERENCES observation_workspace.runs(id), observation_id TEXT, version INTEGER, payload TEXT CHECK(payload::jsonb IS NOT NULL), PRIMARY KEY(run_id,observation_id));
CREATE TABLE observation_workspace.reviews (id TEXT PRIMARY KEY, run_id TEXT REFERENCES observation_workspace.runs(id), observation_id TEXT, payload TEXT CHECK(payload::jsonb IS NOT NULL), storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE);

CREATE TABLE quality_control.datasets (id TEXT PRIMARY KEY, payload TEXT CHECK(payload::jsonb IS NOT NULL), storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE);
CREATE TABLE quality_control.records (dataset_id TEXT REFERENCES quality_control.datasets(id), id TEXT, payload TEXT CHECK(payload::jsonb IS NOT NULL), PRIMARY KEY(dataset_id,id));
CREATE TABLE quality_control.audit (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT CHECK(payload::jsonb IS NOT NULL), storage_sequence BIGINT GENERATED ALWAYS AS IDENTITY UNIQUE);

CREATE TABLE knowledge.sources (id TEXT PRIMARY KEY, payload TEXT NOT NULL CHECK(payload::jsonb IS NOT NULL));
CREATE TABLE knowledge.chunks (source_id TEXT REFERENCES knowledge.sources(id), locator TEXT, text TEXT NOT NULL,
    search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english', text)) STORED, PRIMARY KEY(source_id,locator));
CREATE INDEX knowledge_search ON knowledge.chunks USING GIN(search_vector);
