# Pre-upgrade validation

No application source code was changed before these baseline runs.

| Run | Result | Interpretation |
|---|---|---|
| Exact supplied ZIP | 177 passed, 2 skipped, 7 failed, 46 errors | PRE-EXISTING PACKAGING FAILURE: `data/processed/inspections.parquet` is missing. All seven failures and 46 setup errors reference that missing file. |
| Existing ETL regenerated synthetic fixtures; sandbox run | 171 passed, 2 skipped, 59 errors | ENVIRONMENT FAILURE: Windows temporary-directory permissions. This is not a regression caused by application changes. |
| Regenerated fixtures, unchanged code, explicit test temp directory, outside sandbox | **230 passed, 2 skipped, 15 warnings in 202.00 seconds** | Clean executable baseline. |

Fixture regeneration used the existing `data_engineering.pipeline` with the bundled `data/sample/synthetic_inspections.csv`, `config/schema_mapping.yaml`, `--synthetic`, and `--as-of 2026-09-10`. The fixture is synthetic and is not evidence of a successful real-data migration.

The suite covers API behavior, authentication/CSRF/security headers, chatbot, deterministic analytics and risk, database operations, source normalization, observation intelligence, QC, agent routing, evidence grounding, workflow review gates, optimistic concurrency, retrieval, Redis degradation, and Spark transformations. These are automated test results, not a production security certification or a real SME approval.

Runtime in this test is whole-suite duration, not user-request latency. A comparable retrieval-quality and request-latency benchmark remains to be recorded. Frontend hash baseline is captured in `production-regression-hashes.json`; browser verification remains required after the upgrade.

Raw logs and JUnit XML are retained in the task workspace under `work/production-baseline.*`, `work/production-seeded-baseline.*`, and `work/production-clean-baseline.*`. Reports should be copied into final validation artifacts. No upgraded test result should overwrite or be presented as the baseline.
