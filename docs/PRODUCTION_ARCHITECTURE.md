# RegInsight AI upgraded architecture

Implementation status and acceptance gaps are tracked in `PRODUCTION_UPGRADE_STATUS.md`. This describes the current code, not a claim of production certification.

```mermaid
flowchart LR
  Person[Analyst / reviewer] --> UI[Existing React / Vite UI]
  UI --> API[FastAPI: authenticated sessions, role checks, request limits]
  API --> Analytics[Existing deterministic analytics and risk engine]
  API --> Queue[PostgreSQL durable job queue]
  Queue --> Worker[Python worker: leases, heartbeat, retries]
  Worker --> Graph[LangGraph: route, retrieve, generate, evaluate]
  Graph --> Retrieval[Evidence retrieval: full text + exact cosine + rank fusion]
  Retrieval --> PG[(PostgreSQL + pgvector)]
  Graph --> Ollama[Local Ollama: generation and evaluation]
  Graph --> Review[Persisted human review interrupt]
  Review --> UI
  UI --> Decision[Authenticated APPROVE / MODIFY / REJECT]
  Decision --> Queue
  Graph --> Checkpoint[PostgreSQL LangGraph checkpoints]
  Checkpoint --> PG
  Analytics --> PG
  API --> PG
  Graph --> Final[Approved output and preserved evidence trace]
  Final --> UI
  Sources[CSV / XLSX / Parquet / reference documents] --> Ingest[Normalize, validate, retain provenance]
  Ingest --> PG
  Ingest --> Embed[Local semantic embeddings]
  Embed --> PG
```

The UI calls the same domain services for portfolio metrics, inspection evidence and existing review screens. Numerical results remain deterministic. The LLM does not calculate authoritative risk scores or execute arbitrary SQL.

Long-running workflow creation commits a workflow and queue record together. Workers claim rows with `FOR UPDATE SKIP LOCKED`. Each claim has a lease token; stale workers cannot heartbeat or finish a reclaimed job. PostgreSQL advisory locks serialize execution of the same workflow across processes. Maximum attempts default to three. Inference may be repeated after a crash before its result commits: this is not an exactly-once model execution guarantee.

LangGraph runs explicit routing, retrieval, generation and evaluation nodes. Insufficient evidence completes with an abstention. Required review interrupts persist in PostgreSQL. A reviewer decision records the account, rationale, original artifact, optional replacement, artifact version and workflow revision. Optimistic concurrency prevents a second decision on the same version. Approval resumes without a further model rewrite. Rejection regenerates only within the iteration bound.

PostgreSQL schemas retain the existing domain boundaries: `public` for inspection data, accounts, workflows and retrieval; `intelligence` for observation classification and provenance; `observation_workspace` for the existing review demonstration; `quality_control` for QC records/reviews; `knowledge` for source-addressable references; `staging` for imports. File exports are derived outputs, not alternative authoritative databases. Redis is optional cache only.

## Data relationships

```mermaid
erDiagram
  USERS ||--o{ SESSIONS : owns
  USERS ||--o{ WORKFLOW_RUNS : requests
  SESSIONS ||--o{ WORKFLOW_RUNS : initiates
  WORKFLOW_RUNS ||--o{ WORKFLOW_EVENTS : records
  WORKFLOW_RUNS ||--o{ REVIEW_DECISIONS : preserves
  USERS ||--o{ REVIEW_DECISIONS : signs
  WORKFLOW_RUNS ||--o{ BACKGROUND_JOBS : executes
  RETRIEVAL_DOCUMENTS ||--o{ RETRIEVAL_CHUNKS : contains
  EMBEDDING_METADATA ||--o{ RETRIEVAL_CHUNKS : identifies_space
  TEXTS ||--o{ OBSERVATIONS : normalizes
  OBSERVATIONS ||--o{ ORIGINS : retains
  RUNS ||--o{ ASSIGNMENTS : classifies
  TEXTS ||--o{ ASSIGNMENTS : groups
  OBSERVATIONS ||--o{ WEBSITE_REVIEWS : reviews
```

Retrieval stores model identity, model digest, dimensions, chunk text, document metadata, content hash and source locators. Separate embedding spaces prevent comparing vectors from different model versions. The current implementation uses exact cosine search. ANN indexing and large-corpus capacity claims require separate scale testing; eight reference chunks cannot justify either.

## Boundaries and guardrails

- Authenticated individual accounts and server-derived reviewer identity.
- CSRF origin checks, allowed hosts, bounded body size and process-local rate limits.
- Typed requests, allowlisted tools, bounded iteration and provider budgets.
- Evidence/citation and numeric checks, domain restrictions and mandatory high-risk review.
- No arbitrary SQL execution or MCP layer.
- Request IDs, redacted logs, workflow events and stored retrieval traces support investigation.

These checks reduce specific failure modes. They do not prove narrative correctness. The same local model currently generates and judges by default, so its evaluation is not independent; consequential outputs still require an accountable human decision.
