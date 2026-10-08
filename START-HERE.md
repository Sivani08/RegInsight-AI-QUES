# RegInsight AI - local application setup

Startup imports the supplied real inspection records and restores the included real observation snapshot into PostgreSQL before the application starts. The Evidence workspace defaults to supplied inspection data. No synthetic observations are generated or imported by this startup path. Observation counts and inspection counts are separate populations.

For an existing installation missing the observation snapshot, extract this updated release and run:

```powershell
docker compose run --rm --no-deps migrate python -c "from scripts.prepare_workspace import restore_observations; restore_observations()"
```

Use `docker compose build migrate` first if the image was built from an older release. The restore is transactional, verifies real-data provenance and row counts, and is safe to rerun. Refresh the Evidence workspace afterward.

The Windows one-command setup uses Docker Compose for the application, PostgreSQL with pgvector, database migrations, and the workflow worker. Docker Desktop must be installed and running. A local Python environment, Node.js, and a separately installed PostgreSQL server are not required for this setup.

## Start on Windows

1. Install Docker Desktop for Windows and start it. Allow Docker Desktop to use Linux containers.
2. Open PowerShell in the extracted project folder and run:

   ```powershell
   .\Start-RegInsight.ps1
   ```

   The launcher creates a git-ignored `.env` with a random database password when needed, builds the application image, applies migrations, imports the prepared inspection and fiscal-year records into PostgreSQL, starts the services, waits for the health endpoint, and opens `http://127.0.0.1:8018`. The first build needs an internet connection and several GB of free disk space.
3. If an administrator account has not already been created, create one in the project folder:

   ```powershell
   docker compose exec app python scripts/create_user.py --name "Your Name" --role admin
   ```

   Enter and confirm a private access key when prompted; use at least 32 characters. Sign in to the website with that key.

   If setup has already provisioned the initial administrator, do not run this again; sign in with the access key issued during setup.

To use another local port, run `.\Start-RegInsight.ps1 -Port 8021`. Stop the services with `docker compose down`; the PostgreSQL data volume is retained.

The PostgreSQL import loads the included prepared real dataset: 274,886 canonical inspections, their 341,046 original inspection/project source rows and 280,130 citation rows, plus 4,696 annual benchmark rows for FY2023–FY2025. The original source workbooks are not bundled; source rows and provenance are preserved in the prepared Parquet snapshots. The app uses PostgreSQL for inspections, citation evidence, and annual benchmarks. It does not import or query the SQLite database.

## Inspect PostgreSQL locally

The Compose database is also published only to this computer at `127.0.0.1:5432`; it is not exposed to the local network. Connect a database client such as DBeaver Community with:

| Setting | Value |
| --- | --- |
| Host | `127.0.0.1` |
| Port | `5432` |
| Database | `reginsight` |
| Username | `reginsight_viewer` |
| Password | the password you set with `scripts/create_viewer.py` |

First provision the viewer with `docker compose exec app python scripts/create_viewer.py`. Enter a unique password of at least 32 characters and keep it in your password manager. The viewer account is read-only. In DBeaver, expand `Schemas` → `public` → `Tables` for canonical inspections, and `Schemas` → `staging` → `Tables` for source inspection rows, citations, and annual benchmarks. The website and chatbot responses can be checked in the running app at `http://127.0.0.1:8018`; the `admin_chat_history` and `admin_chat_evidence` views show persisted conversation replies and evidence. Copy the queries in `docs/chat-history.sql` into DBeaver.

Example read-only checks in DBeaver's SQL editor:

```sql
SELECT count(*) FROM public.inspections;
SELECT count(*) FROM staging.inspection_source;
SELECT count(*) FROM staging.citation_source;
SELECT year, count(*) AS benchmark_rows, sum(frequency) AS frequency_sum
FROM staging.annual_source GROUP BY year ORDER BY year;
SELECT inspection_id, payload->>'company_name' AS company, payload->>'inspection_date' AS inspection_date
FROM public.inspections ORDER BY inspection_year DESC LIMIT 20;
```

## Optional local chatbot model

The deterministic website can start without Ollama, but the workflow worker and semantic retrieval require Ollama with `nomic-embed-text:latest`. Full release validation also requires the chat model. To enable local chatbot generation, install Ollama, pull `qwen3:1.7b`, and configure the chatbot model using the project's setup script. The model is approximately 1.4 GB; it is not fine-tuned. Chat answers use RegInsight instructions and retrieved evidence, and numerical dashboard answers are selected from backend-calculated statements. An unavailable model does not prevent the rest of the app from starting.

With Ollama running on Windows, use:

```powershell
ollama pull nomic-embed-text:latest
ollama pull qwen3:1.7b
docker compose exec app python scripts/setup_chatbot.py
```

The Compose configuration routes the container to Ollama on the Windows host. Refresh the chatbot and check its status after registration.

## Existing PostgreSQL / local Python setup

Docker is not mandatory if you already have a PostgreSQL server with pgvector and the application dependencies installed. Set `DATABASE_URL`, install `requirements-app.txt` into `.venv`, then launch the host process with:

```powershell
.\Start-RegInsight.ps1 -Local
```

This advanced mode requires a ready PostgreSQL database; it does not provision one.

## Existing application features

Updated 26 September 2026: autoplay, larger and bolder Segoe UI typography, improved alignment and backend-generated graph insights. See `docs/readability-revision.md` for verification details.


The Docker launcher serves the included production frontend. Node.js and Spark are not needed to start the site. Ollama is optional. Docker builds the runtime image and database migrations run automatically.

## Included

- Responsive landing page with a real Three.js 3D scene, pause control, reduced-motion support and a fallback when WebGL is unavailable.
- Default portfolio dashboard with synchronized filters and a conversational analytics copilot.
- Typed semantic plans, bounded conversation references, ranked results, source evidence and reproducible methodology.
- Existing observation review workspace and broader investigation agent.
- The supplied real data: **274,886 canonical inspections**, **133,375 sites**, and a separate **280,114-observation** real snapshot. These populations are different and are never combined into one denominator. This is the source data from the supplied app, not a newly fabricated million-row medical manufacturing dataset.

## Access and security

The launcher binds the website to the local computer. User access keys are stored as digests in PostgreSQL; provision accounts with `scripts/create_user.py` as described above. Do not put access keys or database passwords in source files or URLs.

Sessions use HTTP-only, SameSite=Strict cookies, eight-hour expiry and server-side revocation on logout. Requests are bounded and rate-limited; cross-origin writes and unexpected hosts are rejected. Production mode requires a key of at least 32 characters and sets Secure cookies and HSTS. Serve production behind HTTPS and configure `REGINSIGHT_ALLOWED_HOSTS`; sessions are persisted in PostgreSQL. Rate limits remain process-local; configure shared rate limiting before scaling externally.

Accounts have individual access keys and analyst, reviewer, or admin roles. Chat APIs enforce conversation ownership. Workflow review uses authenticated reviewer identity. Organizational SSO and tenant isolation are not provided. No compliance certification or formal regulatory validation is claimed. External deployment, TLS, SSO and a penetration test were not performed.

## Using the copilot

Open **Portfolio**, apply filters, and use **Ask about this graph** or type a question. Try:

1. “Which sites have the highest risk?”
2. “Why is the first one high?”
3. “Show the inspections.”
4. “What evidence supports that?”
5. “How did you calculate that?”

The answer displays its scope when a follow-up narrows to a site. Changing dashboard filters resets conversation references. Evidence and calculation details expand inline. Observation questions use the separate snapshot; unsupported cross-population filters are rejected explicitly. Citation rate is unavailable in this real dataset because citation-indicator denominators were not supplied; posted citation counts are not substituted.

## Development and validation

See `docs/dashboard-copilot.md`, `docs/upgrade-design.md` and `docs/upgrade-validation.md`. The archived `README.md` and older validation reports describe the supplied baseline; the files above describe this upgrade.

Frontend source is in `frontend/src/experience/`; the actual entry point is `frontend/src/main.jsx`. Rebuild with Node.js 22.12+ using `npm ci` and `npm run build` inside `frontend`.

The new backend endpoint is `POST /api/agent/dashboard-query`. The original `POST /api/agent/query` is retained. `GET /api/semantic/catalog` describes supported concepts and filters. Core conversational analytics use deterministic templates and do not require a paid provider.

## Clean archive validation

Use a separate Compose project and ports to preserve an existing installation:

```powershell
$env:COMPOSE_PROJECT_NAME="reginsight_archive_validation"
$env:REGINSIGHT_DB_PORT="55432"
.\Start-RegInsight.ps1 -Port 18018 -NoBrowser
```

Only remove this temporary project after validation: `docker compose -p reginsight_archive_validation down -v`. Never use `-v` on a development database.

Chat questions, responses, source snapshots, citations, retrieval queries, calculated results and statuses are committed to PostgreSQL. The assistant restores the latest conversation for the current filters. Reset starts a new conversation without deleting audit history. Interrupted executions are marked failed by the worker after five minutes. The existing chatbot uses deterministic analytics or project-reference keyword retrieval; workflow retrieval uses pgvector/full-text hybrid search. Scores unavailable to a path stay NULL. Chatbot replies do not currently start human-review workflows, so their workflow IDs remain NULL. Workflow drafts, reviews and checkpoints remain in the existing workflow tables.

To index the included project references for workflow hybrid retrieval, run `docker compose exec app python scripts/index_workflow_sources.py` after installing the embedding model. This explicit step creates pgvector embeddings in PostgreSQL; it does not index all inspection records or bundle model binaries.
