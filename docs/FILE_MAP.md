# File map

The table covers every significant source, configuration, data contract and operational file retained in the clean repository. Generated caches, installed dependencies and compiled Python bytecode are excluded from delivery packaging.

| File | Layer | What it does | Why it exists | Called/imported by | Dependencies | Removal |
|---|---|---|---|---|---|---|
| `frontend/src/main.jsx` | frontend | Mounts `Experience` | Sole browser entry point | Browser | React | Required |
| `frontend/src/experience/Experience.jsx` | frontend | Landing, access, portfolio and workspace navigation | Current visual reference | `main.jsx` | React, Recharts, Three.js | Required |
| `frontend/src/experience/Chatbot.jsx` | frontend | Streams evidence and local chat answer events | User-facing assistant | `Experience.jsx` | Fetch, AbortController | Required |
| `frontend/src/reginsight/RegInsight.jsx` | frontend | Evidence browsing and review workspace | Current evidence workflow | `Experience.jsx` | Resource hooks, charts | Required |
| `backend/api/main.py` | API | Creates FastAPI and registers routes | Backend composition root | Uvicorn | FastAPI, Store, Intelligence | Required |
| `backend/api/security.py` | API/security | Access key, sessions, host/body/rate/CSP controls | Local deployment boundary | `main.py` | Starlette, HMAC | Required |
| `backend/database/store.py` | data | Canonical inspection/evidence persistence | Durable source of inspection facts | API/services | SQLAlchemy, SQLite/PostgreSQL | Required |
| `backend/database/load.py` | data | Transactional Parquet loader | Restores prepared datasets | bootstrap/prepare | SQLAlchemy, Arrow | Required |
| `backend/database/retrieval_mart.py` | data | Versioned narrow inspection projection | Bounded large-dataset retrieval | app lifespan/prepare | SQLAlchemy | Required |
| `backend/services/intelligence.py` | domain | Shared risk/trend/recurrence facade | Keeps domain calls consistent | APIs/agents | metrics, risk, mart | Required |
| `backend/services/dashboard_insights.py` | domain | Typed plan/query/evidence loop | Dashboard analytics and context | dashboard assistant/chat | semantic, SQL | Required |
| `backend/analytics/dashboard_queries.py` | analytics | SQL aggregates/ranking/scope caches | Measured portfolio outputs | Intelligence/DashboardInsights | SQLAlchemy, risk engine | Required |
| `backend/risk/engine.py` | domain rules | Six-factor score and coverage | Sole numerical risk authority | services/analytics | YAML, metrics | Required |
| `backend/semantic/catalog.py` | semantic | Metric/focus/dimension whitelist | Prevents unsupported query semantics | planner/models | None | Required |
| `backend/semantic/models.py` | semantic | Request/plan/response validation | Typed API contract | planner/API | Pydantic | Required |
| `backend/semantic/planner.py` | semantic | Question/context to QueryPlan | Deterministic query routing | DashboardInsights | resolver/models | Required |
| `backend/agents/chatbot.py` | AI agent | Evidence retrieval and local-model validation | Chat agent | chatbot API | httpx, Ollama, Pydantic | Required |
| `backend/agents/investigator.py` | agent | Company/site investigation orchestration | Agent endpoint | agent API | tool registry, services | Required |
| `backend/agents/observation_investigator.py` | agent | Observation-specific routing | Specialized evidence questions | investigator | ObservationTools | Required |
| `backend/tools/registry.py` | tools | Six portfolio tools and traces | Typed deterministic tool calls | investigator/API | Pydantic | Required |
| `backend/tools/observation_tools.py` | tools | Nine observation tools | Typed snapshot operations | observation investigator/API | observation service | Required |
| `backend/services/observation_intelligence.py` | observation | Cached tags, groups, aggregates | Separate observation snapshot | APIs/tools/CLI | SQLite, classifier, Grouper | Required |
| `backend/genai/contracts.py` | AI contracts | Strict classification/provenance schemas | Rejects invented evidence | providers/services | Pydantic | Required |
| `backend/genai/classifier.py` | AI | Provider selection and fallback | Bounded optional AI | observation service/API | providers, request gate | Required |
| `backend/genai/providers.py` | AI | Provider envelopes | OpenAI/Claude/Gemini/local/Ollama adapters | classifier/compat API | httpx | Required |
| `backend/genai/request_gate.py` | AI/security | Request/rate/token budget | Prevents uncontrolled outbound calls | providers/classifier | httpx | Required |
| `backend/cache/redis_cache.py` | cache | Optional Redis + local single-flight cache | Acceleration with DB fallback | services | redis optional | Required for configured cache; safe disabled |
| `backend/cache/retrieval.py` | cache | Scope/revision cache identity | Avoid stale analytics | Dashboard/workspace | Redis cache | Required |
| `backend/services/knowledge.py` | reference | FTS5 source search | Supplied PDF/PPTX references | QC API | SQLite FTS5 | Required for optional reference search |
| `backend/services/qc_data.py` | QC | QC imports/audit/reviews | Retained operational QC API | QC API | SQLite/Pydantic | Required for QC API |
| `backend/services/qc_signals.py` | QC | Thresholds and exploratory forecast | Retained QC analytics | QC API | rules/cache | Required for QC API |
| `data_engineering/pipeline.py` | ETL | Read/map/validate/quarantine/export | Canonical data preparation | CLI/bootstrap/tests | Spark/pandas/Arrow | Required for reimport |
| `data_engineering/intelligence_sources.py` | ETL | Observation source discovery/normalization | Snapshot ingestion | tagging CLI/service | SQLite/Arrow/openpyxl | Required for observation rebuild |
| `data_engineering/dataset_inventory.py` | ETL | Source and artifact inventory | Provenance and portable paths | ingestion CLI | Arrow/openpyxl | Supporting |
| `data_engineering/build_knowledge.py` | ETL/reference | PDF page/PPTX slide FTS index | Optional knowledge search preparation | operator command | pypdf/zip XML | Supporting |
| `config/risk_weights.yaml` | config | Score weights/bands | Business rule configuration | risk engine | YAML | Required |
| `config/schema_mapping.yaml` | config | ETL field mapping | Source contract | pipeline | YAML | Required for reimport |
| `config/chat_knowledge.json` | config | Curated chat evidence | Definitions/methodology retrieval | chatbot agent | JSON | Required for reference chat |
| `config/RegInsight.Modelfile` | config | Local model registration | Domain system prompt/model name | setup chatbot | Ollama | Supporting |
| `data/inspections.db` | data | Prepared real inspection snapshot | Immediate desktop demo | Store/start-real | SQLite | Required for packaged demo |
| `data/intelligence/intelligence.db` | data | Prepared observation corpus/run | Evidence workspace | observation APIs | SQLite | Required for observation workspace |
| `data/real/annual_benchmarks.json` | data | Annual industry aggregates | Benchmarks API | benchmark route | JSON | Required for benchmarks |
| `frontend/dist/` | generated UI | Reference production assets | FastAPI serves without Node | `main.py` | Vite output | Required for no-build demo |
| `scripts/bootstrap.py` | ops | Preserve/load dataset and serve | Simple local startup | operator | Python | Supporting |
| `scripts/prepare_workspace.py` | ops | Restore prepared snapshots | Dataset initialization | launcher | Store/intelligence | Supporting |
| `scripts/prepare_retrieval.py` | ops | Build indexes/projections | Query performance | launcher | mart/retrieval | Supporting |
| `scripts/package_chatbot.py` | ops | Read-lock/backup/package/verify ZIP | Reproducible delivery | operator | zip/sqlite | Supporting |
| `scripts/verify_ui_regression.py` | ops/test | Browser comparison | Release QA | operator | Playwright/Pillow | Supporting |
| `Start-RegInsight.ps1` | ops | Primary Windows launcher | Human-friendly startup | operator | PowerShell | Required on Windows |
| `start-real.ps1` | ops | Local model/real DB launcher | Real-data desktop path | operator | PowerShell/Ollama | Supporting |
| `Dockerfile` / `docker-compose.yml` | deployment | Containerized app, PostgreSQL/pgvector, and worker | Default Windows startup | `Start-RegInsight.ps1` | Docker/Java/Postgres | Required for default startup |
| `tests/` | test | Unit/integration/acceptance checks | Regression evidence | pytest | Test dependencies | Supporting |

The detailed code excerpts and execution paths for the most important files are in `TECHNICAL_WALKTHROUGH.md` and `EXECUTION_FLOW.md`. The removed legacy UI is documented in `CLEANUP_REPORT.md`.
