CREATE TABLE chat_sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    workflow_id TEXT REFERENCES workflow_runs(id),
    title TEXT NOT NULL,
    filters JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'CLOSED')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_activity_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (id, user_id)
);
CREATE INDEX chat_sessions_owner ON chat_sessions(user_id, last_activity_at DESC);
CREATE INDEX chat_sessions_workflow ON chat_sessions(workflow_id) WHERE workflow_id IS NOT NULL;

CREATE TABLE chat_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    sequence_number INTEGER NOT NULL CHECK (sequence_number > 0),
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL DEFAULT '',
    request_id TEXT NOT NULL,
    reply_to_id TEXT REFERENCES chat_messages(id),
    workflow_id TEXT REFERENCES workflow_runs(id),
    status TEXT NOT NULL CHECK (status IN ('RUNNING', 'COMPLETED', 'FAILED')),
    route TEXT,
    agent_name TEXT,
    service_name TEXT,
    model_name TEXT,
    retrieval_mode TEXT,
    response_mode TEXT,
    error_message TEXT,
    input_token_count INTEGER,
    output_token_count INTEGER,
    total_token_count INTEGER,
    latency_ms DOUBLE PRECISION,
    guardrail_checks JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    FOREIGN KEY (session_id, user_id) REFERENCES chat_sessions(id, user_id),
    UNIQUE (session_id, sequence_number),
    UNIQUE (request_id, role)
);
CREATE INDEX chat_messages_owner ON chat_messages(user_id, created_at DESC);
CREATE INDEX chat_messages_workflow ON chat_messages(workflow_id) WHERE workflow_id IS NOT NULL;
CREATE INDEX chat_messages_created ON chat_messages(created_at DESC);
CREATE INDEX chat_messages_pending ON chat_messages(started_at) WHERE status = 'RUNNING';

CREATE TABLE chat_retrieval_events (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id TEXT NOT NULL UNIQUE REFERENCES chat_messages(id),
    request_id TEXT NOT NULL,
    retrieval_mode TEXT NOT NULL,
    query_text TEXT NOT NULL,
    filters JSONB NOT NULL,
    candidate_count INTEGER,
    selected_count INTEGER NOT NULL,
    candidates JSONB NOT NULL,
    latency_ms DOUBLE PRECISION,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE chat_message_evidence (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES chat_messages(id),
    source_id TEXT NOT NULL,
    chunk_id TEXT,
    document_id TEXT,
    observation_id TEXT,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    locator TEXT,
    evidence_text TEXT NOT NULL,
    source_metadata JSONB NOT NULL,
    vector_score DOUBLE PRECISION,
    keyword_score DOUBLE PRECISION,
    hybrid_score DOUBLE PRECISION,
    final_score DOUBLE PRECISION,
    rank INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (message_id, source_id)
);
CREATE TABLE chat_message_citations (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES chat_messages(id),
    citation_id TEXT NOT NULL,
    display_order INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    FOREIGN KEY (message_id, citation_id) REFERENCES chat_message_evidence(message_id, source_id),
    UNIQUE (message_id, citation_id)
);
CREATE TABLE chat_tool_executions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    message_id TEXT NOT NULL REFERENCES chat_messages(id),
    request_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    service_name TEXT NOT NULL,
    input_summary JSONB NOT NULL,
    output_summary JSONB NOT NULL,
    evidence_snapshot_id TEXT REFERENCES evidence(analysis_id),
    status TEXT NOT NULL CHECK (status IN ('COMPLETED', 'FAILED')),
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    latency_ms DOUBLE PRECISION
);
CREATE INDEX chat_tools_message ON chat_tool_executions(message_id);

CREATE VIEW admin_chat_history AS
SELECT s.id session_id, s.user_id, u.name user_name,
       q.sequence_number, q.id user_message_id, a.id assistant_message_id,
       q.content user_question, a.content assistant_response,
       q.created_at asked_at, a.completed_at answered_at,
       a.request_id, a.route, a.agent_name, a.service_name, a.model_name,
       a.retrieval_mode, a.response_mode,
       (SELECT count(*) FROM chat_message_evidence e WHERE e.message_id = a.id) evidence_count,
       (SELECT count(*) FROM chat_message_citations c WHERE c.message_id = a.id) citation_count,
       a.latency_ms, a.workflow_id, w.status review_status,
       a.status response_status, a.error_message,
       a.input_token_count, a.output_token_count, a.total_token_count
FROM chat_sessions s
JOIN users u ON u.id = s.user_id
JOIN chat_messages q ON q.session_id = s.id AND q.role = 'user'
LEFT JOIN chat_messages a ON a.reply_to_id = q.id AND a.role = 'assistant'
LEFT JOIN workflow_runs w ON w.id = a.workflow_id;

CREATE VIEW admin_chat_evidence AS
SELECT a.session_id, a.user_id, a.id message_id,
       q.content question, a.content assistant_response,
       c.citation_id, e.source_id, e.source_name, e.source_type, e.locator,
       e.chunk_id, e.document_id, e.observation_id, e.evidence_text,
       e.vector_score, e.keyword_score, e.hybrid_score, e.final_score,
       a.retrieval_mode, e.rank
FROM chat_message_evidence e
JOIN chat_messages a ON a.id = e.message_id
JOIN chat_messages q ON q.id = a.reply_to_id
LEFT JOIN chat_message_citations c ON c.message_id = a.id AND c.citation_id = e.source_id;
