# Cleanup report

## Removed files

| Category | Count | Evidence |
|---|---:|---|
| Unmounted legacy frontend shell/pages/components/services/assets | 17 | `main.jsx` imports only `experience/`; no dynamic discovery, route or test loads the removed tree |
| Obsolete `legacy_dashboard` method and unused `metrics` import | 1 code path | No callers outside its definition; active dashboard uses `dashboard_queries.dashboard` |

No database, prompt, API router, agent, tool, source asset used by the mounted UI, or uncertainty-classified file was deleted. Test-generated `__pycache__` and `node_modules` are excluded from delivery packaging.

## Changed files

| File | Change | Behavioural impact |
|---|---|---|
| `backend/api/agent.py` | Tool discovery is generated from executable `ObservationTools.registry` | Fixes missing schemas; no tool behavior change |
| `backend/api/benchmarks.py` | Fingerprint-matched fallback to packaged `data/real/annual_benchmarks.json` | Restores benchmark visibility after DB relocation |
| `start-real.ps1` | Correct absolute Python handling, packaged DB fallback, real-dataset validation | Makes the launcher match delivered files |
| `data_engineering/dataset_inventory.py` | Resolves relative manifest paths against project root | Removes source-machine path dependence |
| `data_engineering/intelligence_sources.py` | Uses the shared source-path resolver | Same import semantics with portable manifests |
| `requirements.txt` / `requirements.lock.txt` | Separates app requirements and records installed validated versions | Installation is clearer and reproducible |
| `frontend/src/experience/Experience.jsx` and emitted assets | Synced to final reference | UI preserved; build hashes match |

The complete machine-readable removal list is `work/removals.json` in the task workspace; the final project’s human-readable evidence is this report and FILE_MAP.md.
