# Technical panel walkthrough

## 1. Application purpose
Evidence-grounded regulatory inspection analytics, observation interpretation and human review. Explain numerical authority first: the model does not own counts, denominators or risk scores.

## 2. Technology stack
Python 3.12, FastAPI/Starlette, Pydantic 2, SQLAlchemy 2, pandas/Arrow, optional Spark 4 and Java; React 19, Vite 7, Recharts, Lucide and Three.js. SQLite is the supplied runtime; PostgreSQL and Redis are optional. Exact executed versions are recorded in requirements.lock.txt and TEST_REPORT.md.

## 3. Frontend
`main.jsx` → `Experience.jsx`; local state chooses Landing/Login/Portfolio/Evidence. Evidence renders `reginsight/RegInsight.jsx`. `Chatbot.jsx` owns streaming, cancellation/history and safe text rendering. The complete active frontend source and emitted assets match the final reference.

## 4. Backend
`create_app` installs middleware and routers. Its lifespan constructs Store, attaches a dataset-matching narrow projection, creates Intelligence and initializes the chat agent. Most analytical handlers are synchronous FastAPI handlers; chat is async with blocking retrieval moved to a thread.

## 5. API layer
Typed requests validate limits and scope. `/api/dashboard`, `/api/agent/dashboard-query`, `/api/chatbot/stream`, `/api/agent/query` and `/api/workspace/*` serve the current UI. Observation, benchmark, QC and earlier demo APIs remain registered. See API_ROUTES.md for the route inventory.

## 6. AI architecture
RegInsightChatAgent uses local Ollama and constrained JSON. Classifier wraps optional text providers and validates evidence before accepting tags. `MockProvider` is deterministic keyword logic. The earlier Claude batch has a separate schema/rubric and does not silently accept a rules substitute as a successful Claude run.

## 7. Agent orchestration
InspectionAgent and observation_investigator route by supported rules, not model-generated plans. Tools validates Pydantic arguments and captures status transitions. `/api/agent/tools` now reads the same executable registry, including semantic-group and review tools previously omitted from discovery.

## 8. RAG
Chat has curated token-overlap retrieval plus live SQL facts. Observation similarity has offline lexical/dense cosine grouping. Reference PDFs/PPTX have FTS5 page/slide search through QC endpoints. These are distinct paths; no external vector DB, reranker or semantic answer cache is present.

## 9. Tools
Six portfolio tools plus nine observation tools share one dispatcher. The chat agent invokes DashboardInsights directly; it does not issue LLM tool calls. TOOL_REGISTRY.md lists each schema, implementation and dependency.

## 10. Data layer
Store retains canonical JSON evidence with indexed identity/filter fields. Materialized entity and scope summaries accelerate ranking. observation corpus tables include texts, observations, origins, conflicts, cache, runs, assignments, members and embeddings. website_index is a projection; website_reviews is append-only history. Separate SQLite stores support older observation/QC/reference capabilities.

## 11. Life Sciences semantic/domain layer
Metric definitions, known denominators and grain restrictions live in semantic/catalog.py and models.py. risk/engine.py owns configurable scoring. Original keyword taxonomy remains separate from model classification. Annual frequencies are never used as company inspection counts.

## 12. Security/configuration
Process environment controls providers and database URLs. Credentials do not enter frontend code. Local mode blocks remote API clients; shared-key mode adds HTTP-only sessions and production configuration requires a long key. Same-origin writes, trusted hosts, body/rate limits and CSP are implemented. Multi-user roles and identity-bound signatures are not.

## 13. Error handling
Invalid input/scope produces validation or controlled errors. Provider failures produce labeled deterministic or evidence-only fallback. Database errors return 503. Chat retrieval exceptions become error events. Redis outage falls back to durable storage. Some operator scripts still assume historical local URLs; they are supporting utilities, not automatic deployment steps.

## 14. Scalability
Prepared projections, exact-scope caches and bounded pages reduce repeated payload scans. Scope materialization can still be expensive on a cold large filter. SQLite writes and in-process jobs/sessions constrain concurrency. The local model has a one-generation semaphore and 45-second deadline. No load-test, multi-worker coordination or production SLA is claimed.

## 15. End-to-end example
Ask “What is the OAI rate?” in Chatbot. `send` → `/api/chatbot/stream` → `RegInsightChatAgent.retrieve` → `DashboardInsights.query` → validated plan and `dashboard_queries.aggregate` → known-classification denominator → D1 source with an allowed exact statement → Ollama → validation → visible source-linked answer. Compare this with “What does OAI mean?”, which retrieves K2 from the curated knowledge file and uses no portfolio denominator.

Use IMPORTANT_FILES_CHEATSHEET.md for rapid source lookup and FILE_MAP.md for code excerpts, dependencies and significance. Refer to current validation, not inherited screenshots or historical acceptance JSON, when answering “How do we know it works?”
