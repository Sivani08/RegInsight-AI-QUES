"""Authenticated workflows, durable jobs and semantic evidence storage."""
from alembic import op
revision = '0002_workflow_storage'
down_revision = '0001_domain_storage'
branch_labels = None
depends_on = None


def upgrade():
    op.get_bind().exec_driver_sql('''
    CREATE TABLE users (id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('analyst','reviewer','admin')),
        key_digest TEXT NOT NULL UNIQUE, active BOOLEAN NOT NULL DEFAULT true, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE TABLE sessions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), token_digest TEXT NOT NULL UNIQUE,
        expires_at TIMESTAMPTZ NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE INDEX session_expiry ON sessions(expires_at);
    CREATE TABLE workflow_runs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), session_id TEXT NOT NULL REFERENCES sessions(id),
        status TEXT NOT NULL, revision INTEGER NOT NULL, payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE INDEX workflow_owner_status ON workflow_runs(user_id,status);
    CREATE TABLE workflow_events (workflow_id TEXT REFERENCES workflow_runs(id), sequence INTEGER, event TEXT NOT NULL,
        payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(), PRIMARY KEY(workflow_id,sequence));
    CREATE TABLE review_decisions (id TEXT PRIMARY KEY, workflow_id TEXT NOT NULL REFERENCES workflow_runs(id),
        reviewer_id TEXT NOT NULL REFERENCES users(id), artifact_version INTEGER NOT NULL,
        workflow_revision INTEGER NOT NULL, decision TEXT NOT NULL CHECK(decision IN ('APPROVE','MODIFY','REJECT')),
        rationale TEXT NOT NULL, original_output TEXT NOT NULL, modified_output TEXT,
        idempotency_key TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE(workflow_id,idempotency_key), UNIQUE(workflow_id,artifact_version));
    CREATE TABLE background_jobs (id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id), job_type TEXT NOT NULL,
        workflow_id TEXT REFERENCES workflow_runs(id), payload JSONB NOT NULL, status TEXT NOT NULL DEFAULT 'QUEUED',
        idempotency_key TEXT UNIQUE NOT NULL, attempts INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
        available_at TIMESTAMPTZ NOT NULL DEFAULT now(), leased_until TIMESTAMPTZ, lease_token TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), started_at TIMESTAMPTZ, finished_at TIMESTAMPTZ,
        error TEXT, result_reference TEXT);
    CREATE INDEX available_jobs ON background_jobs(status,available_at);
    CREATE TABLE embedding_metadata (space TEXT PRIMARY KEY, model TEXT NOT NULL, version TEXT NOT NULL,
        dimensions INTEGER NOT NULL CHECK(dimensions>0), created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE TABLE retrieval_documents (id TEXT PRIMARY KEY, source_name TEXT NOT NULL, metadata JSONB NOT NULL,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE TABLE retrieval_chunks (space TEXT REFERENCES embedding_metadata(space), chunk_id TEXT,
        document_id TEXT NOT NULL REFERENCES retrieval_documents(id), text TEXT NOT NULL,
        payload JSONB NOT NULL, metadata JSONB NOT NULL, content_hash TEXT NOT NULL,
        chunking_version TEXT NOT NULL, embedding vector NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
        search_vector TSVECTOR GENERATED ALWAYS AS (to_tsvector('english',text)) STORED,
        PRIMARY KEY(space,chunk_id));
    CREATE INDEX retrieval_text_search ON retrieval_chunks USING GIN(search_vector);
    CREATE INDEX retrieval_metadata ON retrieval_chunks USING GIN(metadata);
    CREATE INDEX retrieval_document ON retrieval_chunks(document_id);
    CREATE TABLE audit_events (id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, user_id TEXT REFERENCES users(id),
        request_id TEXT, workflow_id TEXT REFERENCES workflow_runs(id), event TEXT NOT NULL, payload JSONB NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    CREATE TABLE evaluation_runs (id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), kind TEXT NOT NULL,
        payload JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
    ''')


def downgrade():
    raise RuntimeError('Review and workflow history must be retained. Restore a verified backup for rollback.')
