# Five-minute technical explanation

“RegInsight combines deterministic inspection analytics with a bounded local chat model. Its key architectural decision is that the model explains evidence; it does not calculate or overwrite the risk score.

The Windows entry point is Start-RegInsight.ps1. It prepares the supplied SQLite snapshots and retrieval indexes, then starts backend/api/main.py through Uvicorn. FastAPI serves both the APIs and the Vite build. In the browser, frontend/src/main.jsx mounts Experience.jsx. That file owns the landing screen, access-key login and two current workspaces: Portfolio and Evidence workspace.

When the Portfolio opens, its resource hook calls /api/dashboard. Intelligence.dashboard delegates to analytics/dashboard_queries.py. SQL aggregates provide counts and known-denominator rates. Materialized site summaries avoid repeatedly processing the complete evidence payload. risk/engine.py remains the one implementation of the six-factor score, with missing factors and coverage disclosed.

Clicking ‘Ask about this graph’ calls /api/agent/dashboard-query. DashboardInsights.query loads any saved context, and semantic/planner.py turns the supported question into a typed QueryPlan. It can resolve ‘the first one’ from a previous ranked result. The plan only permits declared metrics, filters and analytical grains. The service executes ordinary SQL and deterministic calculations, composes a response, checks its numeric values and stores supporting evidence. That entire analytics-copilot path works without an LLM.

The AI chatbot takes a different route. Chatbot.jsx posts the question, filters and prior context to /api/chatbot/stream. RegInsightChatAgent.retrieve selects curated project references using token overlap, or asks DashboardInsights for live facts. It streams that evidence to the browser before waiting for local Ollama. generate requests structured JSON. validate rejects unknown citations, unsupported numeric tokens and altered calculated statements. For calculated data, the model must select an allowed answer verbatim. A timeout or bad answer produces a clearly labeled evidence-only response.

The Evidence workspace reads a separate observation snapshot. intelligence_sources.py preserves original observation identities and source metadata while deduplicating normalized text. observation_intelligence.py uses validated classification caches and local similarity grouping. By default Grouper uses lexical cosine vectors; an optional preinstalled sentence-transformer can be used. There is no external vector database and no generic vector-query-to-chat pipeline. Browse/search uses SQLite indexes and optional FTS5 trigram acceleration.

The investigation endpoint routes through InspectionAgent and its observation delegate. They are bounded rule-based orchestrators with 15 typed tools, not autonomous model planners. Each call is validated and traced. Optional observation models can interpret text, but numerical metrics remain in the deterministic services.

Review decisions are appended with revision checks in api/workspace.py. They preserve original classification evidence and record the local reviewer’s statement. Authentication is a shared-key local-team boundary, not enterprise SSO or an electronic-signature system.

For handover, FILE_MAP.md explains the remaining files, EXECUTION_FLOW.md follows the user journeys, and TEST_REPORT.md separates executed tests from unavailable infrastructure. The cleanup removes only the unmounted older UI, retains the active visual implementation, and fixes discovered packaging and tool-discovery defects. Production deployment still needs organization-specific identity, operations and domain validation.”
