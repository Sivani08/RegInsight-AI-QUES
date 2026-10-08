# Validation on 2026-09-20

The bundled backend suite passed 110 tests with 2 skips. The skips are the existing tests that require the absent real-corpus database in the archive. The post-integration subset passed 59 tests with 1 skip. Compile-time validation passed with `python -m compileall -q backend data_engineering tests`.

The frontend production build passed with Vite 7. The build used the existing dependency installation through a local junction because copying the dependency tree would exceed available temporary disk space; the junction is not part of the deliverable archive.

A generated scale fixture processed 100,000 observation occurrences and 1,000 unique texts. The first rules run made no provider calls. The second run reused all 1,000 classification entries and all 1,000 cached vectors. The end-to-end regression covers dataset discovery, quarantine, grouping, AI validation, SQLite persistence, API group/tag reads, agent retrieval, and saved evidence.

The installed local Ollama model `qwen3:1.7b` was reachable. Its sample response invented keywords and a patient-safety conclusion; Pydantic validation rejected it and the classifier returned deterministic rules with `fallback=true` and `Human review required`. This is expected validation behavior. No Gemini API key was present during this run, so Gemini transport was exercised through mocked provider tests and remains opt-in.

The five configured source workbook hashes match the existing audited source evaluation. The archive includes prepared imports for those workbooks; the raw Excel originals are external to the archive and are not copied into the deliverable. The bundled corpus snapshot contains the synthetic data and prepared real-source artifacts available in the repository.
