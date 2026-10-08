# Observation intelligence upgrade

The existing application now has one validated observation intelligence path. Source rows are normalized into the immutable SQLite corpus, text is deduplicated by SHA-256, deterministic taxonomy signals are computed, local vectors are cached, semantic groups are assigned with bounded candidate search, and only representative text is eligible for a configured AI provider. Every provider result is validated by the shared Pydantic contract before persistence.

The provider order is Gemini, optional Ollama fallback, then deterministic rules. Gemini uses `AI_PROVIDER=gemini`, `AI_MODEL=gemini-2.5-flash-lite`, and a server-side `AI_API_KEY`; outbound calls still require `AI_ENABLE_REMOTE=true` or the CLI `--enable-ai`. Ollama is loopback-only and remains keyless. Set `OLLAMA_FALLBACK_MODEL` to an installed model when Gemini failures should try local AI before rules. A missing key or invalid output never breaks the application.

The shared contract is `ObservationTag` (also exported as `ObservationClassification`). It forbids unknown fields, uses bounded strings and lists, validates confidence, checks exact evidence against normalized text, checks keywords, rejects instruction text as evidence, and records provider, model, taxonomy version, prompt version, timestamp, fallback state, review state, dataset, and record identities. AI severity is analytical and human-review required. The deterministic risk engine is unchanged and never consumes the AI severity field.

All compatible CSV, XLSX, and Parquet files under the data tree are discovered. Rows with unsupported schemas, missing source identity, invalid frequencies, invalid identifiers, or empty observations are stored in `quarantine`; no row is silently discarded. Source provenance includes file, sheet, row, source observation ID, inspection, company, site, year, product, and inspection type where supplied. Audited Excel workbooks are reused only when their SHA-256 matches the prepared import audit.

The current page adds semantic group counts, severity distribution, review filtering, group filtering, quarantine access, and an expanded evidence/provenance view. The agent can retrieve recurring themes, severity distribution, semantic groups, human-review observations, similar observations, and supporting evidence through typed tools. Numerical claims continue to come from database tools.

For a fresh run:

```powershell
python -m data_engineering.tag_observations --dataset all --provider rules --max-requests 0
python -m data_engineering.tag_observations --dataset all --provider gemini --enable-ai --max-requests 20
```

The second command is intentionally budgeted for a free API. Repeated text and group members are processed locally. Cache keys include normalized text, model, taxonomy version, and prompt version. Set `AI_CACHE_ENABLED=false` for a deliberate reclassification after changing provider configuration.
