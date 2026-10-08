> Historical document from the final reference. Statements and old validation results below are not current certification. Use README.md and docs/TEST_REPORT.md for this delivery.

# Regulatory Inspection Insights Assistant

Local AI without an API key: run `scripts/setup-ollama.ps1` once, then `scripts/start-real.ps1`. The launcher selects Ollama with Qwen3 1.7B, installed and smoke-tested on this machine. See [local setup, hardware requirements and validation status](docs/local-ai.md).

A working graduation prototype for data engineering, regulatory analytics, observation interpretation and tool-based investigation.

**Two separate datasets are available.** The original synthetic demonstration remains in data/processed. The five supplied workbooks have been evaluated and imported into data/real, containing 274,886 distinct inspections and linked citation evidence. Use start-real.ps1 for the real-data database. See [source evaluation and integration](docs/source-evaluation.md). Scores are prioritization heuristics, not regulatory determinations.

## RegInsight AI website (2026-09-21)

The default frontend is now the RegInsight AI website with live inspection browsing, source-linked evidence, risk analytics and persistent human review. See [website setup, deployment boundaries and validation](docs/reginsight-website.md). The built frontend and font license are included.

## Observation intelligence upgrade (2026-09-20)

The existing application now uses one validated intelligence path for observation classification, the dashboard, and agent interpretation. Source rows are normalized into an immutable SQLite corpus, text is deduplicated by SHA-256, deterministic taxonomy signals are computed, local vectors are cached, semantic groups use bounded candidate search, and only representative text is eligible for a configured AI provider. See [upgrade details](docs/intelligence-upgrade-2026-09-20.md) and [validation results](docs/validation-2026-09-20.md).

Gemini is the recommended provider: `AI_PROVIDER=gemini`, `AI_MODEL=gemini-2.5-flash-lite`, and a server-side `AI_API_KEY`. Outbound calls require `AI_ENABLE_REMOTE=true` or the CLI `--enable-ai`. Set `OLLAMA_FALLBACK_MODEL` to an installed local model for Gemini → Ollama → rules fallback. Invalid output is rejected and falls back to validated rules.

```powershell
python -m data_engineering.tag_observations --dataset all --provider rules --max-requests 0
python -m data_engineering.tag_observations --dataset all --provider gemini --enable-ai --max-requests 20
```

Classification caches include normalized text, model, taxonomy version, and prompt version. Set `AI_CACHE_ENABLED=false` for a deliberate reclassification after changing provider configuration.

## What it does

* PySpark maps and validates CSV, Excel and Parquet, normalizes records, quarantines invalid/duplicate rows, uses joins/windows/ranking and produces analytical Parquet plus a quality report.
* SQLAlchemy stores one active dataset in PostgreSQL or SQLite, with transactional replacement.
* Deterministic services calculate citation/OAI rates, observation burden, recurrence, trends and explainable risk scores.
* React provides Dashboard, Inspections, Risk Intelligence, Trends, Recurring Risks, AI Agent, Annual Benchmarks and Data Quality views. Company/site profiles include histories and score explanations.
* Six typed agent tools investigate companies and sites, compare companies, rank priorities and save evidence snapshots.
* Observation interpretation supports rules without API credentials, plus optional OpenAI, Claude and local model adapters.
* Rule-based alerts flag high risk, repeated OAI, citation-rate increases, recurring data-integrity signals and recent high-severity text signals.

## Architecture

```text
CSV / Excel / Parquet → schema mapping → PySpark ETL
                                      ├─ quarantine + data quality
                                      └─ canonical Parquet → PostgreSQL / SQLite
                                                           └─ deterministic analytics + risk
Observation text → provider / keyword fallback ──────────────└─ investigation tools → evidence
                                                                                  ↓
                                                                               FastAPI
                                                                                  ↓
                                                                             React dashboard
```

Data engineering computes facts. The risk engine calculates indicators. GenAI interprets observation text. The agent investigates evidence.

See [architecture and methodology](docs/architecture.md) and [data contract](docs/data-contract.md).

## Technology

Python 3.12, FastAPI, Pydantic, SQLAlchemy 2, PySpark 4, pandas, Arrow, PostgreSQL/SQLite; React 19, Vite 7, Recharts and Lucide.

Prerequisites: Python 3.12, Java 17 or 21 recommended (the local pipeline was also verified with Java 22), and Node 24 or Node >=22.12. Set JAVA_HOME to the JDK directory if Java is not discovered.

## Local installation

Run commands from the repository root. No paid API is required.

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
Set-Location frontend
npm.cmd ci
npm.cmd run build
Set-Location ..
.venv\Scripts\python.exe scripts/bootstrap.py --serve --host 127.0.0.1
```

Linux/macOS:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python scripts/bootstrap.py --serve --host 127.0.0.1
```

Open [the application](http://127.0.0.1:8000) and [interactive API docs](http://127.0.0.1:8000/docs).

Bootstrap retains an existing database. If no dataset is loaded, it loads included processed data, or generates the synthetic data and runs Spark if processed files are absent. Its default demonstration reference date is 2026-09-10; use `--as-of YYYY-MM-DD` when generating a different synthetic snapshot. Bootstrap never replaces a loaded dataset automatically.

The delivered source archive includes a built frontend and processed synthetic files, so you can skip the Node build for an immediate demonstration. Rebuild after frontend changes.

Environment variables are read from the process. `.env.example` is a reference; it is **not automatically loaded** by local Python commands. Set variables explicitly in PowerShell/Bash, or use the appropriate deployment environment. Docker Compose reads its own `.env` substitutions.

## Running Phase 1 explicitly

```powershell
.venv\Scripts\python.exe -m data_engineering.sample
.venv\Scripts\python.exe -m data_engineering.pipeline --input data/sample/synthetic_inspections.csv --mapping config/schema_mapping.yaml --output data/processed --as-of 2026-09-10 --synthetic
.venv\Scripts\python.exe -m backend.database.load --processed data/processed
```

Use the corresponding `.venv/bin/python` path on Linux/macOS. On Windows, Spark transforms the records and Arrow writes them in bounded batches, avoiding a dependency on winutils. On Linux, Spark writes native distributed Parquet.

The sample reconciles 213 source rows into 211 valid inspections, one rejected record and one duplicate, including one unknown classification retained as null. All numbers here were verified from the included pipeline output.

## Using real FDA-style data

1. Keep the original file. Input must have **one row per inspection**.
2. Copy `config/schema_mapping.yaml` and map canonical fields to your exact source column names. Absent optional fields stay null. At least one company, site or FEI identity must be mapped.
3. Run into a new output directory, without `--synthetic`:

```powershell
.venv\Scripts\python.exe -m data_engineering.pipeline --input data/raw/inspections.xlsx --mapping config/my_mapping.yaml --output data/processed_real --as-of 2026-09-10
```

4. Review `quality.json`, `rejected.parquet`, and `duplicates.parquet`. Conflicting repeated inspection IDs need review. Observation-level source tables must be aggregated upstream before ingestion.
5. Explicitly replace the active database:

```powershell
.venv\Scripts\python.exe -m backend.database.load --processed data/processed_real
```

6. Refresh the application. The banner changes to USER-SUPPLIED DATA. Existing saved investigations retain their original records and dataset ID.

Supported date formats: ISO date, US MM/dd/yyyy, ISO timestamp without timezone. Ambiguous formats are not guessed. XLSX works out of the box; legacy XLS needs the optional `xlrd` dependency. Malformed input produces an actionable CLI exception rather than silently loading a partial file. Missing values are never fabricated.

## PostgreSQL and Docker

For a running PostgreSQL instance:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://insights:password@localhost:5432/insights"
$env:ALLOW_SQLITE_FALLBACK = "false"
.venv\Scripts\python.exe -m backend.database.load
.venv\Scripts\python.exe -m uvicorn backend.api.main:app --host 127.0.0.1 --port 8000
```

Default local SQLite is `data/inspections.db`. When PostgreSQL is unavailable and ALLOW_SQLITE_FALLBACK=true, a prominent warning identifies the SQLite fallback; datasets are not silently copied between databases.

Full-stack Docker path:

```bash
docker compose up --build
```

Compose builds React, installs Java 17/Python/Spark, starts PostgreSQL with a health check, loads the demonstration on first use and serves the application on loopback port 8000. It uses persistent PostgreSQL and processed-data volumes. Configure POSTGRES_PASSWORD for your environment. Docker/PostgreSQL execution was not verified in this workspace because Docker is unavailable. The delivered Docker recipe is not a claim of a tested deployment.

Sites' Worker runtime cannot host the Python/JVM/PostgreSQL stack. No incomplete static-only hosted substitute was published.

## Separate development servers

Backend:

```powershell
.venv\Scripts\python.exe -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
```

Frontend, in another terminal:

```powershell
Set-Location frontend
npm.cmd run dev
```

Vite proxies /api to the backend. The built frontend is served directly by FastAPI in normal demo mode.

## Risk methodology

Edit `config/risk_weights.yaml`. The backend validates weights and thresholds. Restart the backend after config changes. Each saved investigation captures the actual configuration.

Default weights: citation history 25; classification history 25; recurrence 20; recency 10; observation burden 10; negative citation trend 10. Weighted components normalize to 0–100 over available factors; unavailable components are disclosed with coverage. Empty/unmeasurable records produce INSUFFICIENT DATA.

* Citation rate denominator: records with known citation flags.
* OAI rate denominator: records with known NAI/VAI/OAI classification.
* Classification factor: (OAI + 0.4 × VAI) / known classifications.
* Recurrence: maximum repeated keyword theme beyond its first inspection / 3, capped at 1.
* Recency: latest adverse dated inspection decays linearly over 730 days.
* Severity component: average known observation count / 5, capped at 1. This is a burden proxy, not clinical severity.
* Negative trend: positive citation-rate change between the latest two usable years.

Bands use the unrounded score: LOW <30; MODERATE <60; HIGH <80; CRITICAL >=80. A score of 86 is therefore CRITICAL, correcting the inconsistent HIGH label in the example brief.

The ETL reference date is fixed, so repeated requests with identical records/configuration produce identical scores. Annual risk scores use cumulative history through each year, without future records; annual rates/counts use that year's records. Partial years and unavailable history are disclosed.

## Agent and evidence

The agent is a bounded **rule-based tool orchestrator**, not an LLM planner and not a generic chatbot. It resolves known company/site/FEI names, applies requested year bounds, selects investigation/ranking/comparison/theme-change workflows, validates tool arguments and records each executed tool.

Tools:

1. search_inspections
2. calculate_risk
3. analyze_trend
4. find_recurring_risks
5. analyze_observation
6. get_evidence

Numbers in answers are formatted from tool results. The LLM receives observation excerpts only. Optional AI output is validated against Pydantic and must quote a verbatim source excerpt. It cannot replace scores, rates or counts. A versioned keyword taxonomy drives recurrence/risk independently of model output.

Each investigation stores its source inspections, original rows, metrics, themes, configuration, dataset fingerprint, reference date and tool trace. Evidence is paginated for display, while calculated metrics use the full saved record set. Explicitly named companies override previously selected UI context.

Supported examples:

* Why is Aster Therapeutics considered high risk?
* Show recurring deficiencies for Aster Site 1.
* How has Aster's risk changed since 2022?
* Compare Aster Therapeutics and Northstar Biologics.
* Which sites should management investigate first?
* Which risk themes increased over the last three years?

Unknown or ambiguous entities return a clarification error rather than invented records. The agent does not support arbitrary natural-language database queries.

## Optional AI providers

Default: AI_PROVIDER=mock, a deterministic keyword fallback.

Optional process environment:

```text
AI_PROVIDER=openai | claude | local | mock
AI_API_KEY=server-side secret
AI_MODEL=an available model from your selected provider
AI_TIMEOUT_SECONDS=20
AI_BASE_URL=http://localhost:11434/v1/chat/completions
```

AI_BASE_URL applies only to LocalProvider. OpenAI uses the Responses API with a strict JSON schema; Claude uses the Messages API; local models use an OpenAI-compatible chat endpoint. Model choice is explicit. No keys are compiled into React. Provider failures and unverifiable output return a visible rule-fallback notice. Confidence is uncalibrated, and rule matching can misread negation. Human review is required.

Paid provider calls were not made or live-tested. Contract/failure tests use controlled provider doubles. Provider API references: [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs) and [Claude Messages API](https://platform.claude.com/docs/en/api/messages).

## API

Interactive OpenAPI docs: /docs; schema: /openapi.json.

| Endpoint | Purpose |
| --- | --- |
| GET /api/health | Database/fallback and dataset status |
| GET /api/dashboard | Portfolio metrics, trends and risk register |
| GET /api/inspections | Company/site/FEI/country/product/project/classification/year filters; pagination |
| GET /api/companies, /api/sites | Ranked company/site summaries |
| GET /api/profile | Company or site investigation profile |
| GET /api/risk | Score, components, coverage and measured denominators |
| GET /api/trends | Annual analysis, theme and year bounds |
| GET /api/recurrence | Distinct theme matches grouped by company/site/year/country/product |
| POST /api/observations/analyze | Typed observation analysis |
| POST /api/agent/query | Agent investigation |
| GET /api/agent/tools | Tool argument schemas |
| GET /api/evidence/{analysis_id} | Saved evidence, default 25 records per page |
| GET /api/data-quality | Quality metrics and paginated quarantine review |
| GET /api/alerts | Deterministic site alerts |

## Testing and demonstration

```powershell
.venv\Scripts\python.exe -m pytest tests -q -p no:cacheprovider --basetemp .test-tmp
Set-Location frontend
npm.cmd run build
```

Run ETL first for its output integration test. Spark tests start a local JVM and require loopback sockets. If Windows reports a temporary-directory permission conflict, choose a new workspace `--basetemp` directory. Pytest removes its basetemp, so use a dedicated test scratch directory only.

Tests cover file readers, Spark normalization/rejection, output reconciliation, transactional database loading, deterministic scoring and bands, nullable denominators, historical isolation, recurrence, APIs, provider failures, tool argument validation, context resolution, alerts, comparison, rankings and the evidence acceptance scenario.

Demonstrate:

1. Open Dashboard and inspect measured portfolio totals.
2. Select Lupin Limited for the supplied dataset, or Aster Therapeutics for the synthetic demo.
3. Review history, citation/OAI rates, themes, trend and “Why this score?”
4. Choose “Ask agent about this company” and submit the question.
5. Review the tool trace, score explanation, observation interpretation and trend.
6. Click “View evidence,” expand a source inspection, and inspect its raw record.
7. Open Data Quality to review source reconciliation; the synthetic demo also includes intentional rejects and duplicates.

See [validation record](docs/validation.md) for the checks actually executed.

## Repository layout

```text
backend/
  api/           FastAPI routes
  agents/        bounded investigation orchestration
  tools/         Pydantic tool registry
  analytics/     measured metrics, taxonomy, recurrence, trends, alerts
  risk/          configurable scoring
  genai/         provider abstraction and fallback
  services/      shared application services
  database/      SQLAlchemy storage and loader
config/          schema mapping, risk weights, alert rules
data_engineering/ sample generator and Spark pipeline
data/            sample, processed and optional raw inputs
frontend/src/    components, pages and API client
scripts/         bootstrap
tests/           unit, integration and acceptance checks
docs/            architecture, data contract, validation
```

## Limitations and future improvements

* This is a local prototype without authentication, authorization or a multi-user deployment security model. Default local access is loopback.
* Native Spark transformations are implemented, but pandas reads source files and application analytics materialize filtered records. The 341,046 project rows were normalized to 274,886 inspections. Materialized entity summaries and lightweight analytical queries are implemented. Concurrent-user performance remains unbenchmarked.
* One active dataset; no automatic incremental ingestion, CDC, migrations or background refresh. Do not replace datasets concurrently with investigations.
* Risk weights, thresholds, keyword themes and severity proxy need domain validation and calibration. Missing information limits comparisons.
* No claim is made that keyword matches represent confirmed deficiencies. Recurrence is by distinct inspection, not independently parsed observation count.
* Free-form LLM planning, RAG/vector retrieval, production monitoring, multi-tenant access and calibrated model evaluation are future work.
* User-supplied FDA-style exports were imported without independently authenticating provenance. No cloud deployment or live paid-model validation was performed.


## Delivery package

The source ZIP includes code, compiled frontend assets and the small synthetic dataset. Large real-data files and installed dependencies are excluded. The prepared real database remains in the local project under data/real. Rebuild it elsewhere using the five original workbooks and the source-evaluation instructions.

To start the prepared local installation from this project folder (Redis starts automatically when its bundled runtime is present):

```powershell
.\scripts\start-real.ps1
```

The root command is also supported. On a fresh machine, create the local environment first, then run the same command:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\scripts\start-real.ps1
```

Performance limitation: unfiltered portfolio recurrence exceeded a 60-second live check before a query projection optimization. The final acceptance check covers company-scoped recurrence. Company selection is recommended for interactive recurrence/evidence analysis; full-population recurrence latency remains unverified after optimization.

## Complete observation tagging workflow

Open **Observation Workspace** for the separate 72-observation synthetic demonstration, persisted category/theme/severity tags, pandas summaries, source references and expert review. See [workflow, provenance, Claude execution and acceptance status](docs/observation-workflow.md). Live Claude and independent expert assessment remain pending until credentials and expert reviews are provided.

## All-source observation intelligence upgrade (2026-09-18)

The new Observation intelligence page processes all compatible prepared datasets together, while preserving their real, synthetic and annual grains. It adds strict Pydantic validation, versioned taxonomy, evidence/rationale, bounded provider requests, persistent text caching, local grouping, deterministic recurrence and seven observation tools. The existing risk formula and six portfolio tools remain unchanged.

Run `python -m data_engineering.tag_observations --provider rules --dataset all` before opening the new page on a fresh installation. This uses no API key. Outputs are a snapshot database, JSON report and compressed JSONL export. Optional Gemini requests require deliberate enablement and an account key.

See [end-to-end implementation](docs/observation-intelligence.md), [official provider assessment](docs/provider-assessment.md), [upgrade results and limitations](docs/upgrade-report.md) and [validation](docs/validation.md). The current local corpus has 284,983 records/templates; 22,027 unique texts. All current classifications are rules, with no remote API calls. The source ZIP excludes large real-data databases and exports; retain the local data or rerun the documented source import.

## Redis retrieval cache

Optional Redis now caches observation pages, analytics, similar evidence and validated classifications. New completed runs automatically use fresh cache keys; outages fall back to the database. Docker Compose includes Redis, while direct Python startup remains keyless and Redis-optional. See [configuration and behavior](docs/redis-cache.md). Install test dependencies with `pip install -r requirements-test.txt` before running the full suite.
