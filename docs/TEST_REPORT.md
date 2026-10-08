# Test report

## Executed status

| Area | Status | Evidence |
|---|---|---|
| Frontend build | PASS | Vite build completed; emitted asset hashes are identical to the final reference build |
| Backend startup | PASS | Uvicorn startup and health endpoint returned 200 |
| API smoke | PASS | Health, auth status, dashboard, observation summary/page, tool discovery, chat status, QC knowledge and benchmarks returned successfully |
| Python suite before cleanup | PASS | 192 passed, 2 skipped; 14 warnings |
| Clean-project repair subset | PASS | 7 passed; benchmark fingerprint fix, Spark scratch isolation, cleanup regressions and provider initialization |
| Browser request-cache tests | PASS | 3 passed |
| Local chat | PASS | Two live questions returned `local_llm` with validated answer events |
| Deterministic tool paths | PASS | Full suite and executable-registry regression coverage |
| RAG/reference search | PARTIAL | Chat reference retrieval and calculated evidence pass; optional PDF/PPTX FTS5 index requires explicit `build_knowledge.py` run |
| Database | PASS | Packaged SQLite databases open and pass `PRAGMA quick_check`; PostgreSQL not run |
| UI regression | PARTIAL / UNVERIFIED | Build is byte-identical; automated screenshot comparator reached Portfolio but did not obtain an Evidence record in its final run |
| Remote AI providers | BLOCKED — intentionally not called | No credential used; provider contracts and fallback paths are tested |
| Docker deployment | BLOCKED — Docker unavailable | Compose recipe retained and documented, but not executed here |

## Known limitations

* The prepared real database is packaged as `data/inspections.db`; original workbook paths are not included. Reimport requires the five source workbooks or a new mapping.
* The visible current UI is `Experience` plus the evidence workspace. The previous `App.jsx` page tree was removed because it was not mounted by `main.jsx`; its backend APIs remain where they serve retained capabilities.
* Local model latency is variable and model availability is external to the repository. A failed model call shows evidence or rules output explicitly.
* The supplied external configuration contains local workbook paths from the source machine. The cleaned manifest uses project-relative `data/raw` names and the ingestion resolver supports absolute operator paths.
* Production use still needs enterprise authentication/authorization, worker coordination, migrations, monitoring, calibrated domain validation and deployment security review.
