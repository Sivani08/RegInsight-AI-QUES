# Execution flow

## Startup and navigation

`Start-RegInsight.cmd` → `Start-RegInsight.ps1` → check Docker Desktop → create `.env` with a random PostgreSQL password if needed → `docker compose up --build --detach` → PostgreSQL health check → schema/checkpoint migrations → import 274,886 canonical inspections, embedded inspection/citation source rows, and fiscal-year benchmarks into PostgreSQL → build analytics/retrieval projections → API plus workflow worker → poll `/api/health` → open the browser. The optional `-Local` mode instead requires a prepared Python environment and an existing PostgreSQL/pgvector database before it runs migrations and Uvicorn.

The initial UI displays Landing. `enter()` chooses login or workspace using `/api/auth/status`. Successful `/api/auth/login` creates a session cookie. Workspace navigation changes React state between Portfolio and `RegInsight` (Evidence workspace). The final reference's removed access-status indicator remains removed.

## Chat query loop

```text
User sends a question
  frontend/src/experience/Chatbot.jsx:send
    POST /api/chatbot/stream (question, filters, history, context)
      backend/api/chatbot.py:chat → events
        backend/agents/chatbot.py:RegInsightChatAgent.stream
          retrieve → curated token-overlap references, or DashboardInsights.query
          emit evidence event before generation
          generate → Ollama /api/chat, constrained JSON
          validate → known citations, supported numeric tokens, D1 exact allowed statement
          emit local_llm answer OR explicit evidence_only fallback
      NDJSON → Chatbot.accept → sources, calculated result and answer rendering
```

Only previous user questions help short-reference retrieval; prior generated answers are not source evidence. Analytics context contains a saved analysis ID. Filters invalidate stale scope. The chat semaphore permits one generation at a time per agent instance; a busy model returns evidence-only instead of queueing. Generation has a 45-second overall timeout. Retrieval is performed in a worker thread and does not have the same generation deadline.

## Chart question / deterministic analytics

`Experience.jsx:ChartCard` asks a focused question → `AnalyticsCopilot.send` → POST `/api/agent/dashboard-query` → `api/dashboard_assistant.py:dashboard_query` → `DashboardInsights.query` → saved context lookup → `semantic/planner.py:plan` and `semantic/resolver.py:resolve` → `QueryPlan` validation → `execute` → `dashboard_queries.aggregate/ranked_sites/risk_distribution` OR `observation_insights` → `compose` → `validate_numeric` → `Store.save_evidence` → typed response → charts/tables and evidence sections. No LLM is called for this path.

“Why is the first one high?” resolves the first saved ranked entity using `result_references`; it does not ask a model to invent an entity or score.

## Company/site investigation

Evidence assistant `reginsight/Assistant.jsx:ask` → POST `/api/agent/query` → `InspectionAgent.query` → resolve company/site and year bounds → `Tools.call` validates each argument → search, risk, trend, recurrence, optional bounded observation interpretation → `Store.save_evidence` → get_evidence verification and trace update → response. For a large dataset, record-level unscoped portfolio investigations are deliberately rejected with a clarification message.

Observation-specific questions delegate to `observation_investigator.investigate` → latest completed run → `ObservationTools` → tags/groups/recurrence/similarity/review sampling → saved evidence. The routing is rules-based; it does not call a supervisor LLM.

## Browse, filter and review evidence

`RegInsight.jsx` resource hooks → GET `/api/workspace/summary` and `/api/workspace/observations` → `workspace.cohort` → completed run plus `website_index` → optional trigram candidate accelerator plus literal final predicate → SQL count/sort/page → `observation_intelligence.tags` validates stored tags → source panel. `Evidence.jsx:Review.save` posts `/api/workspace/reviews` → source identity check → `BEGIN IMMEDIATE` revision comparison → append decision and timestamp. A stale revision returns 409. The reviewer identity is self-reported, not a verified signature.

## Observation ingest and classification

`python -m data_engineering.tag_observations` → inventory/discovery → `intelligence_sources.ingest/add` → preserve distinct record identities and source origins, deduplicate text → `observation_intelligence.run/_run` → local Grouper vectors/groups → cache lookup → Classifier for representative text (rules for eligible remaining group members) → `Classification.verify_evidence` → durable tag assignments and completed run → JSON/gzip exports and read APIs. Unsupported inputs are recorded; annual frequencies remain annual-template grain.

## Backend-only retained journeys

* Annual benchmarks: `/api/benchmarks` → adjacent annual file, or fingerprint-matched packaged `data/real` → deterministic frequency/trend totals. No company risk recalculation uses these aggregates.
* Earlier observation demo: `/api/observation-workspace` family → `services/observations.py` → rules or explicit Claude Sonnet batch → pandas summary/review/export. This older screen was already unreachable in the supplied final UI.
* Clinical QC: `/api/qc/import` or CSV/operator-configured sync → `qc_data` validation/provenance → `qc_signals.analyze` thresholds and optional exploratory forecast → audit/review/export.
* Reference search: `python -m data_engineering.build_knowledge` → PDF-page/PPTX-slide FTS5 index → `/api/qc/knowledge` → quoted matches and source download. The packaged final reference has source documents but no built knowledge DB; run this explicit preparation command to enable that optional feature.
