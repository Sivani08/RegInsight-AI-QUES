# RegInsight AI Agentic Upgrade

## Delivered

This project now includes an evidence-grounded workflow for regulatory investigation. A request is classified by an ordered routing rubric, relevant SQLite vector evidence is retrieved with trace metadata, a specialist agent produces a structured draft, and a separate judge evaluates the draft before it can enter human review. The existing RegInsight interface remains in place; the workflow panel is mounted inside the existing evidence/review experience.

The workflow persists state and events in SQLite, supports optimistic concurrency, records retrieval and operational traces, and exposes review actions for approve, revision required, and reject. Approval finalizes the already evaluated artifact without another model call. Revision is bounded by the configured iteration limit.

## Main implementation areas

- `backend/workflows/`: schemas, routing rubric, SQLite state store, orchestration service, evaluation judge, and factory wiring.
- `backend/rag/`: deterministic local embeddings, policy-aware chunking, SQLite vector storage, search, and retrieval trace generation.
- `backend/agents/`: Evidence, Inspection Assessment, Data Analytics, and Unsupported Domain specialist contracts.
- `backend/api/`: workflow creation, status, evidence, evaluation, trace, review, and resume endpoints.
- `frontend/src/reginsight/WorkflowReview.jsx`: workflow status, evidence, evaluation, and human review controls.
- `config/`: routing policy and generation/judge prompt templates.
- `scripts/index_workflow_sources.py`: document ingestion and indexing.
- `evaluation/workflow_cases.json`: development routing and retrieval cases.

## Validation completed

- Backend regression suite: **147 passed, 1 skipped**.
- Frontend production build: completed successfully with Vite.
- Frontend request-cache tests: **3 passed**.
- Browser smoke check at 1440px and 390px: workflow panel visible, no horizontal overflow, human-review section present, and no browser errors.
- Development evaluation: routing accuracy **1.0** across 12 cases; retrieval metrics are recorded in `workflow-evaluation-results.json`.
- Live local Ollama workflow: actual generation and separate judge calls completed with a score of **91.25/100 (PASS)**.

## Runtime steps

1. Install the requirements from the project files.
2. Start Ollama and make `reginsight-chat:qwen3-1.7b` available, or configure the local model endpoint used by the project.
3. Index the source documents with `scripts/index_workflow_sources.py`.
4. Start the existing FastAPI and frontend application using the supplied start scripts.
5. Have an authorized SME complete the human review action for production decisions.

## Production follow-up

The live model demonstration used an explicitly labelled automated demonstration actor. It is evidence that the workflow works end to end, not a production approval. Before release, perform SME acceptance testing, configure authentication and retention, review the indexed source corpus, and set the deployment data directory. The included development retrieval metrics are smoke-test measurements and are not production quality claims.
