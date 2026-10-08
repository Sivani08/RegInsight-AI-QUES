# Upgrade validation — 24 September 2026

## Executed checks

- Backend regression command: `.venv/Scripts/python.exe -m pytest -q --ignore=tests/test_spark_validation.py`.
- Result: **155 passed, 2 skipped**, 12 dependency deprecation warnings, 21.35 seconds.
- Included 44 new dashboard/observation tests: semantic aliases, invalid plans and filters, SQL-versus-existing metric parity, graph focus contracts, bounded ranking/pagination/history, numeric substitution rejection, multi-turn site/theme/similarity context, observation scope consistency, access-key enforcement and revocation, origin validation, security headers and production fail-closed behavior.
- Existing investigation-agent, database, review workspace, QC, provider, Redis cache and source-adapter regressions are included in the passing run.
- Spark/JVM execution was excluded: PySpark is not installed in this runtime. The prepared existing Spark output reconciliation test passed; the ETL itself was not re-executed.
- The two skips are the legacy real-database test expecting `data/real/inspections.db` (this package uses `data/inspections.db`) and the legacy all-source tagging assertion (the supplied exported tag snapshot is explicitly real-only). The all-source test now explicitly checks that precondition. Dedicated live real-data smoke checks cover this package instead.
- Production Vite build passed. Three.js is a separate lazy-loaded chunk; its 529.92 kB uncompressed size produces a bundle-size advisory (132.23 kB gzip). No build errors.
- Initial dependency installation reported zero npm vulnerabilities; no external penetration test was conducted.
- Isolated Chromium browser checked desktop 1440x1000 and mobile 390x844: landing renders, WebGL canvas exists, pause works, reduced-motion defaults to paused, dashboard loads, ranked-site follow-up works, no horizontal viewport overflow, no JavaScript page errors.
- Screenshots are in `docs/screenshots/`.

## Live data and limitations

The original archive was restored without invented records: 274,886 inspections, 133,375 sites and a separate 280,114-observation real snapshot. Counts and the first-ranked site's risk explanation were checked through the live API. All nine graph focuses are exercised by `scripts/final_smoke.py`; timings and status results are recorded in `docs/upgrade-real-smoke.json`.

No paid AI API was called. The new copilot uses bounded deterministic templates and semantic rules. External deployment, HTTPS termination, SSO, multi-user authorization, million-row throughput and Spark execution remain unverified. Shared-key access is a local/trusted-team gate, not a compliance-certified identity system. The archived baseline validation documents are historical and are not claims about checks rerun for this upgrade.
