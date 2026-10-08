# Validation record

Verified locally on 2026-09-10.

## Executed

* Python 3.12 virtual environment with requirements.lock.txt capturing installed versions.
* Real PySpark 4.0.4 ETL execution, using Java 22 on Windows. CSV → cleaning/validation/windows/joins → canonical Parquet and quarantine.
* Output reconciliation: 213 source rows = 211 valid inspections + 1 rejected + 1 duplicate; 1 unknown classification retained as null.
* CSV, XLSX and Parquet reader tests.
* Complete pytest suite: **23 passed**, including Spark validation, database, deterministic risk, trends, recurrence, APIs, observation fallback, agent tools, context override, evidence and alerts.
* Two non-failing third-party test-client deprecation warnings were emitted.
* React/Vite production build succeeded using bundled Node 24.19.0. The system Node 22.11 is too old; use Node >=22.12 or 24 for builds.
* The final build produces separate application, vendor and chart bundles.
* npm audit reported **0 vulnerabilities**.
* Local server and frontend assets served successfully. The optional live HTTP check was blocked by automatic approval review due to a usage-limit error. No acceptance.json was generated.

## Acceptance coverage

The provided live-check script is designed to retrieve the dashboard, selects the highest-ranked company, retrieves its profile, asks the agent why it is high risk, compares its risk object against the profile, retrieves all evidence pages, reconciles OAI and citation denominators with the evidence records, and verifies all six tools were executed.

This verifies the backend acceptance chain and that compiled frontend assets are served. It does not claim automated browser clicking or screenshot-based visual verification.

## Not executed

* Full real-data Spark reconciliation was executed; see the section below.
* Docker/PostgreSQL integration: Docker is unavailable on this machine.
* Live OpenAI, Claude or local-model inference: no provider credentials/server were configured for validation.
* Browser interaction/visual regression tests.
* Performance/load tests at 341,000+ records.
* Production authentication, authorization or deployment-security certification.

## Reproduce

Follow README.md. After starting the server, run:

```powershell
.venv\Scripts\python.exe scripts/verify_live.py --output docs/acceptance.json
```

The evidence identifier is created at runtime; it is not hard-coded in the application.

## Supplied-workbook validation

The expanded full suite passed: **26 tests**, including Spark tests. After the live check exposed slow site-key lookup and unfiltered portfolio trend recomputation, indexed key resolution and materialized trend reads were implemented. The affected database/alerts/real-data tests passed (3 tests), followed by analytics/real-data tests (5 tests). Two non-failing third-party deprecation warnings remain. Windows also printed an Access denied message after the completed full suite during process cleanup; pytest exited successfully.

Independent full-data PySpark validation passed with 274,886 inspections/distinct IDs, 341,046 source project rows and 280,130 citation rows. The real-data integration test verifies annual citation frequency totals separately from unique Form 483 system totals, paginated inspections, company lookup, nullable risk factors and source evidence.

The initial synthetic live-check limitation above is historical. The final real-data live result is recorded in acceptance-real.json when passed. Use `python scripts/verify_live.py --company-search "Lupin Limited" --output docs/acceptance-real.json` to exercise all six tools on a company with citation text. Browser click tests, live paid providers, Docker and PostgreSQL remain unverified.

Final live HTTP acceptance **passed**: compiled assets, global dashboard/alerts/trends, Lupin Limited profile, six-tool investigation, 42 saved evidence records, risk equality and company-scoped recurrence. See acceptance-real.json. Final API/agent/real-data regression checks: **8 passed**. Unfiltered portfolio recurrence exceeded the initial 60-second live-check timeout; its query now reads fewer fields, but its full-population latency has not been revalidated. Select a company for interactive evidence work.

## Observation workspace release — 2026-09-15

Completed the 72-observation synthetic rules batch with pandas map tagging and groupby/explode summaries. The initial targeted regression suite passed 17 tests. After adding the API review/history test and final pandas mapping, all 7 observation-workspace tests passed. These include recurrence denominators, exact quote validation, negation abstention, stale-review conflicts, original-prediction preservation, evaluation, credential absence and provider failures. Production Vite build succeeded. Live workspace HTTP/export/asset checks passed; see acceptance-observations.json. Browser automation could not initialize (missing runtime assets), so visual interaction verification remains unexecuted. Claude live execution was attempted and refused cleanly because credentials are absent; no Claude success is claimed. No independent expert labels are available.

## Observation intelligence upgrade validation — 2026-09-18

Full suite: **61 passed**, zero failed, two dependency deprecation warnings, 76.47 seconds. This includes Spark, existing API/agent/real-data tests and risk regression. A post-test Java cleanup message reported access denied after pytest successfully exited; no test failed from it. The new suite contains 28 cases covering strict contracts, fabricated evidence, malformed/timeout responses, request budgets, retry/cooldown, text cache isolation, annual grain, dedup/conflict audit, grouping, real corpus completeness, API jobs and risk preservation.

The all-source rules run processed 284,983 records across 22,027 unique texts; a second run achieved 22,027 cache hits, zero requests and 18.829 seconds classification/group-reuse runtime, excluding report/export time. The compressed export contains the complete snapshot. The initial aggregate report ran out of temporary disk space; narrow analytical materialization and compressed exports resolved it.

Production Vite build: 2,176 modules, successful. Live HTTP checks passed: startup, index/compiled assets, observation pages, exact evidence, related observations, annual frequency 41,286 with no invented inspection counts, company themes, full report, four observation-agent questions and evidence tracing, existing dashboard and risk. See [HTTP results](acceptance-intelligence.json). Initial full-page/report responses were about 52 seconds under concurrent full-corpus work; pagination projection and saved-report reuse were subsequently added. Follow-up timings are recorded separately.

Browser automation failed before connecting because its kernel assets could not initialize. Therefore no successful visual click-through is claimed. Credentialed Gemini calls, learned embeddings, PostgreSQL and Docker were not exercised. No classification-accuracy metric can be inferred from software contract tests.

Final follow-up: **28 observation tests passed** after pagination/report changes. The rebuilt frontend assets were served successfully. Saved report 0.047 seconds; company themes 0.656 seconds; global real observation pages 30.797 and 25.078 seconds. Global paging remains a documented performance limitation. All **284,983** exported JSONL records were parsed and their observation IDs checked. See [final timing evidence](acceptance-intelligence-final.json).

## Redis integration validation — 2026-09-18

Full suite: **69 passed, zero failed**, including eight Redis tests; 75.01 seconds, two existing deprecation warnings. Tests use fakeredis and cover hit retrieval, avoiding SQL on a hit, filter/page/run isolation, malformed JSON, typed/evidence validation, TTL, payload limits, outage recovery and durable classification restoration. A real redis-py client connection to the unavailable local service returned safe unavailable status and database fallback. Both Compose files passed structural YAML checks. Docker/real Redis deployment was not exercised: Docker and Redis executables are absent, and no usable WSL distribution was listed. The Python client and test emulator were installed successfully. No speed claim for a real Redis deployment is made.
