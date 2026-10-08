# Upgrade completion report — 2026-09-18

The existing application was extended. Its original deterministic risk engine, risk weights and risk taxonomy are byte-for-byte unchanged against the pre-change manifest. The new observation layer works without an API key. Live AI classification and learned embeddings have not been validated on this machine; current results are rules, not model-generated insights.

## 1–2. Files changed and added

The repository was inspected before modification (69 source/documentation files in the inspection manifest). Exact file lists are in [upgrade-file-manifest.json](upgrade-file-manifest.json). New modules cover contracts, prompt, request gate, classifier, extended taxonomy, grouping, inventory, source normalization, snapshot service/locking, APIs, tools, agent routing, frontend page and tests. Existing providers, original workspace validation, API wiring, agent and frontend navigation were extended. Documentation, environment settings and optional embedding requirements are included. Generated snapshots and acceptance reports are listed separately from implementation intent.

## 3. Dataset inventory

| Input | Prior verified import / role | Included in intelligence |
|---|---|---|
| e4832250-43dc-4c0c-982b-b31f87205869.xlsx | 341,046 inspection/project rows → 274,886 distinct real inspections | Metadata/identities and linked citation evidence |
| e00adefd-b9ce-414f-ae04-21c950fb5f27.xlsx | 280,130 citation rows, 76,162 distinct inspections | 280,114 normalized citation occurrences |
| Inspection_Observations_FY23_0.xlsx | 1,546 annual templates | 1,546 templates, separate aggregate grain |
| inspection_observations_fy24.xlsx | 1,544 annual templates | 1,544 templates, separate aggregate grain |
| inspection_observations_fiscal_year_2025_0.xlsx | 1,606 annual templates | 1,606 templates, separate aggregate grain |
| Original synthetic inspection snapshot | 211 valid inspections | 101 nonempty inspection texts |
| Original observation workspace fixtures | 72 observations / 6 inspections | 72 observations, separate demo scope |

All five workbooks were used through their prepared imports. The inspection workbook and FY23 original could not be reopened during the fresh inventory because Windows returned access errors; prior audited inventory and prepared data were retained. The other three originals were inspected freshly. This is not a claim that every original file was reread successfully in this session. See [inventory](../data/intelligence/inventory.json) and the existing [source evaluation](source-evaluation.md).

The 16 collapsed citation occurrences share inspection/reference/normalized text; all origins remain available. This is a different duplicate definition from exact source-row duplication in the previous ETL. No conflicting records were found in this corpus. Annual frequencies sum to 41,286 citations and must not be treated as 41,286 inspections. Empty-text source records remain represented by inspection metadata where available.

## 4–8. Observations, classifications and cache

| Measure | Completed all-source run |
|---|---:|
| Inspection identities in corpus, including those without text | 275,103 |
| Distinct inspections with tagged text | 76,269 |
| Observation occurrences plus annual templates | 284,983 |
| Unique normalized texts | 22,027 |
| Repeated text occurrences after observation deduplication | 262,956 |
| AI-generated classifications | 0 |
| Rule-generated classifications | 284,983 |
| Unclassified records (included in rules count) | 151,721 |
| Classification failures / fallback records | 0 / 0 |
| API requests | 0 |
| Cache hits on second run | 22,027 |
| Average confidence, uncalibrated | 0.3104 |
| Second classification/group-reuse runtime | 18.829 seconds |

Unclassified is approximately 53.24% of records. The pipeline honestly abstains; software validation does not establish classification accuracy. Severity counts: Low 151,727; Medium 128,553; High 4,666; Critical 37. These are rule outputs for analytical exploration. Low on Unclassified text is not evidence of low actual regulatory risk. The AI severity index is unavailable because no AI-generated tags exist.

The first classification run took 2,310.797 seconds. Its report initially exceeded available temporary disk space. Narrow aggregation fields, explicit connection closure, improved query access and compressed export resolved the failure. The second runtime excludes report/export generation. The gzip export is approximately 68.6 MB and contains every record. Snapshot/run IDs and theme distributions are in [machine-readable report](../data/intelligence/latest/report.json).

## 9–11. Provider, model and free-tier limits

Optional Gemini `gemini-2.5-flash-lite` was chosen for documented structured classification/extraction support, a current standard free tier and documented availability in India. Rules remain the operational default. The [official-source assessment](provider-assessment.md) compares Gemini and Groq across the requested 13 criteria and labels unverified account-specific details explicitly. Free quota does not guarantee completion of the full corpus; billing tier, account limits and provider terms still apply. No signup, credit card flow, credentialed API request or paid operation was performed.

## 12. Pydantic contracts

Added `Classification`, `ObservationTag`, `ObservationRecord`, `TagsPage`, `ThemeMetric`, `MetricsPage`, strict classify/batch/job request-response models and typed observation-tool arguments. The legacy workspace also validates model output before persistence. Extra AI fields, invalid labels/confidence and fabricated evidence are rejected. Provider errors retain safe status classes and rule fallback, without keys or raw provider payloads in logs.

## 13–14. APIs and tools

Added POST classify and batch-tag; GET job status, tags, themes, severity, recurrence, similar observations, report and inventory under `/api/observations`. Seven added tools retrieve tags, recurring themes, severity, year trends, company/site intelligence and similar evidence. Original six tools remain available. The agent preserves saved evidence and tool tracing; numerical answers originate in SQL/tools. See [API and tool details](observation-intelligence.md#apis-and-agent).

## 15. Frontend

Added Observation intelligence navigation, corpus quality summaries, source/AI/rule counts, unclassified percentage, theme charts, severity counts, recurrence, grouping by fiscal year/company/site/product/inspection type, exact-match filters, pagination, provenance and related observations. Agent findings now display tables and quotes. Existing portfolio pages and synthetic Observation Workspace remain. All-source human correction is not implemented; its machine snapshot remains auditable and read-only.

## 16–17. Validation

Full pytest suite: **61 passed, 0 failed**; two dependency deprecation warnings. Post-query-change observation suite: **28 passed, 0 failed**. Existing Spark and risk-regression checks passed. Vite production build passed (2,176 modules). Live HTTP acceptance passed for startup, compiled assets, real observation evidence, annual frequency/grain, recurrence, report, four observation-agent queries, saved tool evidence, dashboard and risk. See [validation](validation.md), [initial HTTP acceptance](acceptance-intelligence.json) and [final HTTP timings](acceptance-intelligence-final.json).

## 18. Remaining limitations

- Real model accuracy is unmeasured; remote adapters use mocked-provider contract tests. No key was supplied or used.
- Learned Sentence Transformer grouping is optional and untested here; the executed default is lexical cosine. Candidate relationships are not regulatory equivalence.
- Two original workbook files were access-restricted in this session; their prepared imports were processed.
- Browser automation failed during runtime initialization, so visual clicks were not verified. Production compilation and actual asset/API delivery passed.
- Large uncached global queries can take seconds to tens of seconds on this machine; saved report reuse substantially reduces repeated report cost. Disk free space was limited. Metrics use bounded output, and evidence lists are paginated samples.
- Company/site names require exact context or recognized names. Agent routing is bounded; no unsupported numerical inference is delegated to an LLM.
- Human review exists in the original synthetic workspace; all-source reviewer adjudication remains a future enhancement.
- No new PostgreSQL/Docker deployment validation was performed. The observation corpus currently uses local SQLite even if the existing portfolio database uses PostgreSQL.
- Per-run request budgets are not global billing/account controls. Crash recovery for a stale API job marker remains an operator procedure.

The current source archive includes implementation, documentation, built frontend and small synthetic demonstration assets. It excludes the large real-data databases and full tagged export; those remain in this local project. Use the documented import to recreate them elsewhere.

Redis update: observation retrieval and validated classification caching are now implemented. The latest suite has **69 passing tests**, superseding the 61-test count above. See [Redis design, setup and scope](redis-cache.md). Redis deployment remains optional; current local execution falls back to the database until a Redis server is available.
