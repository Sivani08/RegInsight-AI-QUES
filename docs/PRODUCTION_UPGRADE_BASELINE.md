# Production upgrade baseline

Source: the supplied `RegInsight-AI-Agentic-Upgrade.zip`, extracted into a separate working directory. The source ZIP and previous delivery remain unchanged. This document describes the pre-upgrade runtime, not a completed target implementation.

## Component decisions

| Component | Current | Decision and migration path |
|---|---|---|
| React/Vite frontend | Existing navigation, charts, evidence and review panels | KEEP. SHA-256 baseline in production-regression-hashes.json; change only authentication/review contracts where necessary. |
| FastAPI | Existing endpoints and local/shared-key security | KEEP endpoints; MODIFY authenticated request context and backend ownership checks. |
| Inspection analytics | SQLAlchemy Store, Python aggregations, materialized summaries | KEEP calculations; MIGRATE connection/schema management to mandatory PostgreSQL with Alembic. |
| Risk | backend/risk/engine.py, YAML weights | KEEP unchanged; compare deterministic outputs. |
| Observation intelligence | SQLite normalized texts, identities, observations, assignments and classification cache | MIGRATE tables and SQL while preserving original text, IDs, classifications and provenance. |
| Reviews | Observation workspace reviews, website reviews, QC audit, workflow artifact reviews | MIGRATE with separate table namespaces; MODIFY transactions, identity, revision and idempotency enforcement. |
| Workflow | Custom persisted Python state machine | MODIFY orchestration into LangGraph nodes, durable PostgreSQL checkpointer, bounded correction and persistent interrupts. Reuse specialist logic and routing. |
| RAG | Local signed feature hashing, SQLite vector BLOBs, exact cosine | REPLACE retrieval backend with PostgreSQL FTS/pgvector; REPLACE lexical hashing with a measured local semantic model. Preserve old approach only for comparison. |
| Model | Ollama structured generation and a real separate LLM judge | KEEP local provider and existing judge semantics; do not mislabel deterministic metrics as judge scores. |
| Cache | Optional Redis; in-process caches | KEEP as disposable acceleration, never authoritative state. Review keys for user/scope isolation. |
| Jobs | FastAPI BackgroundTasks; local batch scripts | REPLACE long-running request tasks with PostgreSQL jobs, leases, bounded retries and worker process. |
| Security | Shared access key and process-local cookie sessions; reviewer names are self-reported | REPLACE account/session persistence; enforce authenticated reviewer permissions and workflow ownership. |
| Deployment | Docker uses plain Postgres image but allows separate local stores | MODIFY pgvector-enabled image, migration startup, worker and explicit model endpoint. REMOVE fallback configuration. |

## SQLite migration inventory

Table names below are taken from source. PostgreSQL schemas separate formerly independent stores to avoid collisions such as `runs`, `reviews`, `cache`, and `datasets`. All schemas live in one authoritative database.

| File | Current database | Tables | Read/write | Called by | PostgreSQL destination |
|---|---|---|---|---|---|
| backend/database/store.py | data/inspections.db | inspections, dataset, evidence | Both | Intelligence, API, data loaders | public inspection tables |
| backend/database/retrieval_mart.py; backend/services/mart.py | inspection database | inspection browsing mart, entity_summaries | Both | Store search, dashboard and entity services | public derived tables, rebuilt transactionally |
| data_engineering/intelligence_sources.py | data/intelligence/intelligence.db | texts, identities, observations, origins, conflicts, corpus, cache, runs, assignments, members, embeddings, quarantine | Both | observation_intelligence, normalization scripts | intelligence schema, same domain records |
| backend/services/website_index.py | intelligence database | website_index, website_index_runs | Both | workspace browsing | intelligence schema, rebuildable index |
| backend/api/workspace.py | intelligence database | website_reviews, retrieval_summaries | Both | evidence workspace API | intelligence schema, authenticated review records |
| backend/services/retrieval_search.py | intelligence database | website_text_search, website_meta_search, FTS triggers | Both | workspace search | PostgreSQL text indexes, preserve literal search semantics |
| backend/services/observations.py | data/observations/workspace.db | runs, tags, reviews | Both | observation workspace API, tag scripts | observation_workspace schema |
| backend/services/qc_data.py | data/qc/qc.db | datasets, records, audit | Both | QC import, signal and review APIs | quality_control schema |
| backend/services/knowledge.py; data_engineering/build_knowledge.py | data/knowledge/knowledge.db | sources, chunks (FTS5) | Both | knowledge search/build | knowledge source/chunk tables with PostgreSQL FTS |
| backend/workflows/repository.py | data/workflows/workflows.db | workflows, workflow_events | Both | workflow service/API | workflow runs/events and immutable review rows |
| backend/rag/repository.py | data/workflows/vectors.db | vector_chunks, embedding_cache | Both | workflow retrieval/indexing | retrieval documents/chunks/model metadata with pgvector |
| data_engineering/source_review.py | source staging file | inspection_source, citation_source, annual_source | Write | one-time source preparation | staging schema; migration-only source reads permitted |
| data_engineering/fda_source_adapter.py | staging and inspections.db | staging reads, inspection writes | Both | data import script | PostgreSQL staging and Store |
| data_engineering/dataset_inventory.py | inspected source databases | source-specific tables | Read | source inventory | migration-only inspection of historical data |
| scripts/collect_evaluation.py | inspections.db | inspection/evidence tables | Read | evaluation export | Store/PostgreSQL reads |
| scripts/prepare_retrieval.py | intelligence database | SQLite catalog/FTS tables | Both | prepare scripts | PostgreSQL migration/index initialization |
| scripts/package_chatbot.py | packaged database files | all source database pages | Read/backup | historical delivery script | replace packaging assumptions; exclude credentials and live database files |

`production-source-inventory.json` records module imports, function names, declared tables and SQLite-specific source lines across 119 Python modules. Runtime callers that obtain connections indirectly must also be migrated; changing only explicit sqlite3 imports is insufficient.

## Migration path and sensitive behavior

1. Record unchanged ZIP tests, then regenerate its missing synthetic Parquet fixtures with its existing ETL and rerun. Preserve both reports.
2. Create explicit Alembic schemas, constraints and indexes. Do not create runtime tables opportunistically.
3. Add one-time source readers with row counts and business-value reconciliation. No source deletion and no dual writes.
4. Migrate Store, observation, QC, knowledge and review SQL in small tested stages; retain deterministic risk/taxonomy code.
5. Introduce authenticated users/sessions and ownership before exposing multi-user workflow endpoints.
6. Migrate retrieval to local semantic embeddings and compare old/FTS/vector/hybrid on the same labelled questions. Do not assume higher quality or lower latency.
7. Move workflow stages to LangGraph with checkpoint persistence; reviewer modifications preserve the original artifact; bounded rejection correction remains auditable.
8. Queue long operations in PostgreSQL with atomic claims and retry-safe identities. Test restart/recovery and duplicate submissions.
9. Run regression and UI hash checks, reconcile data, verify no SQLite runtime imports or fallback configuration, then package.

Regression-sensitive areas: null/unknown classification handling, fixed risk weights, counts and filters, selected observation scope, literal search behavior, taxonomy/evidence quote checks, review revision conflict handling, no post-approval unreviewed model output, reference-only knowledge authority labels, and existing frontend routes/layout.

## Infrastructure observations

No Docker, PostgreSQL command-line tools, installed PostgreSQL service, or WSL distribution was found during initial checks. Ollama and Visual Studio C++ build tools are present. A workspace-local PostgreSQL installation is being prepared; its availability and pgvector compilation must be verified before integration claims. Existing real-data SQLite and Parquet files were omitted from the supplied ZIP, so real-data reconciliation requires separately available originals. Do not treat synthetic fixtures as real regulatory data.
