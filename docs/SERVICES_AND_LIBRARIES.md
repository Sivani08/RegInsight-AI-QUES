# Services, libraries and persistence

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


| Component | Type | Responsibility |
|---|---|---|
| WorkflowService | Application service | Transitions, orchestration, revision bounds, approval gate and finalization |
| RetrievalService | Application service | Ingestion strategy, retrieval thresholds, selected context and trace |
| EvaluationService | Application service | Judge invocation, score aggregation and policy decisions |
| Existing DashboardInsights | Application service | Validated analytical query and numerical authority |
| Existing observation_intelligence | Application service | Snapshot tags, provenance and observation access |
| StructuredLLM | Technical library | Loopback HTTP transport, JSON-schema decoding, bounded concurrency and timing |
| EmbeddingService | Technical capability | Shared deterministic document/query vector encoding |
| chunk_document | Technical capability | Metadata-preserving paragraph/window segmentation |
| VectorRepository | Persistence adapter | SQLite vector and metadata storage, exact cosine query |
| WorkflowRepository | Persistence adapter | Durable state, atomic optimistic writes and append-only events |
| Pydantic schemas | Shared contracts | Requests, analysis, routing, chunks, traces, artifacts and decisions |

Services decide application behavior; libraries perform reusable technical work; repositories isolate storage. Existing classification-provider adapters and legacy chatbot remain unchanged because their contracts differ and remain used. The workflow client deliberately uses local Ollama and a generic structured schema, rather than scattering raw HTTP across specialists.

No new third-party runtime dependency was needed. SQLite, Python standard library, FastAPI, Pydantic, HTTPX, pypdf and the existing frontend toolchain are reused. Ollama is a separately installed local service. Exact declared dependency ranges remain in existing requirements files; no remote provider credential is required for the new workflow.

Database files: data/workflows/workflows.db and vectors.db; override parent with WORKFLOW_DATA_DIR. WAL and transactional revision checks protect local concurrent writes. All new endpoints inherit existing security middleware. Shared-key access is not per-user authorization; filesystem permissions/retention remain deployment responsibilities.
