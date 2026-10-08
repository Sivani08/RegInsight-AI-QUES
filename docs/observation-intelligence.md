# Observation intelligence

This system provides analytical prioritization and observation interpretation. It is not an FDA regulatory determination.

## End-to-end data flow

1. Inventory the five supplied workbooks and prepared data in `data/raw`, `data/real`, `data/processed` and `data/observations`. `config/dataset_sources.json` records original locations. The inventory records schemas, missingness, identities, observation availability and source hashes. Outputs and repeated representations are identified separately.
2. Reuse the existing canonical ETL output. Stream Arrow batches, extract individual linked citation rows, and retain original text and file/sheet/row provenance. Annual FDA citation summaries remain `annual_template` records with frequencies and no invented company, site or inspection ID. The synthetic inspection snapshot and original 72-observation workspace remain separate dataset scopes.
3. Normalize whitespace, retain original text, and hash normalized text with SHA-256. Identify inspections by inspection ID, then FEI/date, then a deterministic company/site/date composite. Conflicting identities are recorded rather than silently overwritten. Observation deduplication uses inspection identity, citation reference, text hash and grain; all source origins remain in SQLite.
4. Process unique texts in bounded batches. Look up the persistent cache using text hash, provider, model, taxonomy version and prompt version. Repeated text consumes no additional provider request. Batching bounds local processing; each uncached text is one request, not a call containing the entire corpus and not Google's paid Batch API.
5. Classify with rules or an explicitly configured provider. The dedicated prompt treats observations as untrusted data, permits only the selected taxonomy and prohibits numerical risk/statistical outputs. Strict Pydantic v2 contracts reject extra fields, invalid severity/theme/confidence, inconsistent categories and invented evidence. Evidence must be verbatim in normalized text. Keywords must occur in the text.
6. Persist source/model/version/time, quote, rationale, confidence, fallback and validation status. Invalid responses fall back to rules. Fallbacks are stored for audit but never cached as successful AI classifications. A later AI run can retry them.
7. Group unique texts within their primary theme. Default `lexical_cosine` uses local word vectors, deterministic candidate selection and representative groups. It is not a learned semantic model. Optional CPU Sentence Transformers uses an already installed local model directory without downloading on startup. Related-text scores refer to the group representative, not necessarily to the selected observation. Similarity does not establish regulatory equivalence.
8. Join assignments back to observation occurrences. SQL calculates theme/year/company/site/product/inspection-type distributions, severity counts, distinct inspections and sites. A narrow temporary analytical table avoids sorting full evidence payloads. All counts are backend facts, not LLM guesses.
9. Expose validated records and metrics through FastAPI and typed agent tools. The Observation intelligence page provides filters, charts, recurrence, evidence and related records. The old Observation Workspace and all portfolio pages remain available.

## Running

Run from the project directory with the installed Python environment:

```powershell
python -m data_engineering.tag_observations --provider rules --dataset all --inventory
python -m data_engineering.tag_observations --provider rules --dataset real --batch-size 1000
```

Default output: `data/intelligence/latest/report.json` and compressed `tags.jsonl.gz`. The SQLite snapshot contains all records, cache, run membership and provenance. Gzip streams the export to reduce disk use. `--output` changes its directory. `--database` selects another snapshot database. `--taxonomy-version` validates the supported taxonomy version; changing taxonomy code/version creates a new cache namespace. A loaded corpus is immutable: import changed inputs into a new database, do not silently mutate an existing run's evidence.

Additional CSV/XLSX/Parquet files in `data/raw` with observation text columns are discovered automatically on a fresh import. Annual inputs with frequencies retain aggregate grain. Inspect unsupported inputs in the quality report. The original canonical ETL/import remains the route for the supplied inspection and citation workbooks.

## Remote AI configuration and limits

The selected optional provider is Gemini, model `gemini-2.5-flash-lite`. See [provider assessment](provider-assessment.md) for official sources and limitations. Default `AI_PROVIDER=rules` and `AI_ENABLE_REMOTE=false`; startup needs no key. Environment variables are read from the process, not automatically from `.env`.

```powershell
$env:AI_PROVIDER='gemini'
$env:AI_MODEL='gemini-2.5-flash-lite'
# Supply AI_API_KEY through your local environment; never commit it.
python -m data_engineering.tag_observations --provider gemini --enable-ai --max-requests 20
```

`AI_MAX_REQUESTS_PER_RUN` includes retries, default 20. `AI_RATE_LIMIT` defaults to 5 requests/minute. `AI_TOKEN_LIMIT_PER_MINUTE` defaults to 20000 estimated tokens; it is an approximate client guard, not a provider tokenizer or quota guarantee. Adjust these to your actual project limits. `AI_MAX_TEXT_LENGTH` defaults to 12000; longer text uses full-text local rules rather than silent truncation. `AI_TIMEOUT_SECONDS` defaults to 30. Up to three attempts handle transient transport failures, timeouts, 429 and selected 5xx responses. Exponential backoff and Retry-After are respected; long cooldowns open the circuit and preserve local fallback. Authentication/configuration failures are not repeatedly retried. Only safe error classes are logged.

A shared OS lock prevents simultaneous batch runs against one snapshot. API job status is persisted. A hard process crash may leave an active API-job marker requiring operator recovery after confirming no process owns the run lock. Limits are per run/process, not an organization-wide billing system. Independent deployments and individual classify requests need deployment-level quotas if publicly exposed. This is a local prototype; do not expose it as an unauthenticated public service.

OpenAI, Claude, Mock and Local adapters remain. A loopback local endpoint can operate with remote access disabled; a non-loopback endpoint requires explicit remote enablement. No model server is bundled. Remote adapters were tested with simulated responses, not with paid or credentialed live requests.

## Contracts and taxonomy

`Classification` is the provider's strict seven-field contract. `ObservationTag` adds trusted provenance and audit fields. `ObservationRecord`, `TagsPage`, `ThemeMetric` and `MetricsPage` validate service outputs. API request models reject arbitrary inputs. Existing legacy AI paths retain their strict contracts.

Taxonomy 2.1 extends the existing themes with materials, packaging/labeling, sanitation, complaints, investigations, environmental monitoring, sterility assurance and production/facility controls. Original risk taxonomy and weights remain unchanged. One primary theme is assigned per text. Ambiguous text may remain Unclassified. Rules confidence is a heuristic, not a calibrated probability. An Unclassified/Low tag means insufficient classification evidence, not demonstrated low regulatory risk.

## Severity, recurrence and risk

“AI-generated severity classification for analytical prioritization. Not an FDA regulatory determination. Human review required.”

The original deterministic risk engine and observation-count burden proxy remain unchanged. The separate AI-derived severity index is the mean of Low=.25, Medium=.50, High=.75, Critical=1.00 over validated AI-generated occurrences in the selected scope. Rules/fallbacks are excluded. With no AI-generated records it is unavailable, not zero.

Recurrence score is `(distinct inspections - 1) / distinct inspections` for a theme/scope, or zero where no inspection denominator exists. The score indicates repetition, not an occurrence rate across all inspected facilities. Annual templates have no inspection recurrence denominator; their frequency totals are reported separately. Repeated text occurrences, duplicate source rows and distinct inspection recurrence are different measures.

## Local embedding option

Install `requirements-embeddings.txt` only if needed and provide an existing `all-MiniLM-L6-v2` model directory using `OBSERVATION_EMBEDDING_MODEL_PATH` or `--embedding-model`. Configure `OBSERVATION_SIMILARITY_THRESHOLD` (default .78). This delivery validates lexical grouping; it does not claim an embedding model was installed or benchmarked. Candidate search is bounded, not exhaustive all-pairs clustering. Changing the model/threshold prevents reuse of earlier group assignments.

## APIs and agent

POST: `/api/observations/classify`, `/api/observations/batch-tag`.
GET: `/api/observations/jobs/{id}`, `/tags`, `/themes`, `/severity`, `/recurrence`, `/similar/{observation_id}`, `/report`, `/inventory` under `/api/observations`.

Metrics support company, site, year/range, theme, severity, dataset, grain, product and inspection type. Observation pages are bounded to 200 records, default 25; group results default to 200 with total group count. API metric aliases return the same typed grouped data, including severity distributions. Similar-record lists are bounded candidate samples.

Seven added typed tools: `get_observation_tags`, `find_recurring_themes`, `get_severity_distribution`, `get_theme_trend`, `get_company_observation_intelligence`, `get_site_observation_intelligence`, `find_similar_observations`. The original six tools remain. Agent queries record tool calls and saved evidence. Use the company/site context for “this company/site”; use an observation ID for precise classification evidence or similarity. Routing is deterministic and bounded; it is not unrestricted natural-language reasoning. Annual benchmark requests use annual grain. Real portfolio questions default to real observations; request “all datasets” to combine scopes.

## Human review and limits

The original synthetic Observation Workspace retains expert corrections and audit history. The all-source intelligence snapshot is read-only machine output with `reviewed=false`; mass review/adjudication is not implemented. A domain expert should evaluate a representative labeled set before using AI tags to prioritize actual compliance decisions. No classification-accuracy claim is made from contract tests.

All five sources were included through their prepared canonical/annual imports. Two original workbooks could not be reopened in this session due to Windows access errors; their prior inventory and prepared data were retained. Fresh original-file verification and prepared-data completeness are distinct. See inventory and upgrade report for exact counts. Empty observations are excluded from tagging, not fabricated. Database and export sizes matter on machines with little free disk space.
