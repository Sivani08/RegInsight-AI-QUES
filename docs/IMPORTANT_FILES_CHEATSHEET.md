# Important files cheat sheet

| File | Remember it as | Critical function |
|---|---|---|
| `frontend/src/main.jsx` | Browser entry point | Mounts `Experience` |
| `frontend/src/experience/Experience.jsx` | Current product shell | Landing, login, Portfolio, Evidence workspace |
| `frontend/src/experience/Chatbot.jsx` | Streaming assistant UI | Sends questions; renders evidence/model/fallback states |
| `frontend/src/reginsight/RegInsight.jsx` | Evidence workspace | Browse, filter, inspect and review observations |
| `backend/api/main.py` | API composition root | Initializes app and registers routes |
| `backend/database/store.py` | Canonical inspection store | SQL persistence and filtered evidence search |
| `backend/services/intelligence.py` | Domain facade | Risk, trend, recurrence, profiles and dashboard calls |
| `backend/services/dashboard_insights.py` | Typed analytics query loop | Plan → SQL → deterministic response → evidence |
| `backend/semantic/planner.py` | Question planner | Maps supported wording/context to a typed plan |
| `backend/analytics/dashboard_queries.py` | Portfolio SQL | Aggregates, ranking and scoped risk summaries |
| `backend/risk/engine.py` | Risk authority | Six-factor weighted score and coverage |
| `backend/agents/chatbot.py` | Chat agent | Retrieves evidence and validates local-model output |
| `backend/agents/investigator.py` | Investigation router | Resolves company/site workflows and saves traces |
| `backend/agents/observation_investigator.py` | Observation router | Routes persisted observation intelligence tools |
| `backend/tools/registry.py` | Portfolio tools | Six typed tools and execution trace |
| `backend/tools/observation_tools.py` | Observation tools | Nine additional typed tools |
| `backend/services/observation_intelligence.py` | Observation pipeline | Caches tags, groups texts, serves aggregates |
| `backend/genai/contracts.py` | AI contracts | Strict evidence/provenance schemas |
| `backend/genai/classifier.py` | Provider selector | Remote/local/rules fallback and cache keying |
| `backend/genai/providers.py` | Provider adapters | Ollama/OpenAI/Claude/Gemini/local envelopes |
| `data_engineering/pipeline.py` | ETL | Normalize, validate, quarantine and export |
| `data_engineering/intelligence_sources.py` | Observation ingestion | Preserve origins/conflicts and deduplicate text |
| `config/risk_weights.yaml` | Risk configuration | Weights, parameters and band thresholds |
| `config/chat_knowledge.json` | Chat reference corpus | Curated definitions/methodology source entries |
| `scripts/prepare_workspace.py` | Snapshot restore | Loads packaged real and observation snapshots |
| `scripts/prepare_retrieval.py` | Index preparation | Builds projections and retrieval indexes |
| `Start-RegInsight.ps1` | Primary launcher | Prepare and serve the local application |
