> Historical source walkthrough, retained for provenance. The inactive App.jsx subtree described below was removed in the 2026-10-04 cleanup. See FILE_MAP.md and TECHNICAL_WALKTHROUGH.md for the current implementation.

# Requirement audit against the supplied image

Reviewed 28 September 2026. This is an evidence-based review of the current source and saved local run metadata. The application was not changed and no remote Claude call was made.

## Verdict

**The project implements the core use case, but the default website does not fully execute the exact mock-data + Claude Sonnet + pandas path named in the image.** That specific path is substantially implemented in the retained observation-demo module; its rules/pandas behavior is tested, but a successful real Sonnet run has not been demonstrated by this review.

The current saved observation snapshot reports `provider=rules`, `model=deterministic`, `status=completed`, `total=280114`, `ai=0`, `rules=280114`, `fallbacks=0`, and `grouping_method=lexical_cosine`. The separate legacy demo database `data/observations/workspace.db` does not currently exist. This matters: code support is different from a prepared, demonstrated run.

## What the image says

The readable row identifies **Regulatory Inspection Insights Assistant**, **Insight Generation**, and: “Derives themes and recurring risk areas from a mock dataset of regulatory inspection observations, tagging by category and severity.” It lists **Business Enablement**, **Regulatory Compliance**, **Python, Claude Sonnet, pandas for tagging/aggregation**, and a **synthetic inspection-observations dataset based on public FDA 483 letter formats**. The row also contains a “Not Started” status cell. Blank colored cells are not interpreted as additional requirements.

## Requirement-by-requirement result

| Requirement | Source implementation | Current/default behavior | Assessment |
|---|---|---|---|
| Regulatory Inspection Insights Assistant | Portfolio, graph copilot, evidence/review workspace and APIs | Current `Experience` shell exposes these core functions | Implemented |
| Insight generation | [[backend/services/dashboard_insights.py#DashboardInsights.compose]]; [[backend/analytics/graph_insights.py#graph_insights]] | Source-derived deterministic text and computed metrics | Implemented; do not label all current narratives LLM-generated |
| Derive themes from observations | [[backend/analytics/observation_rubric.py#tag_rules]]; [[backend/genai/classifier.py#Classifier.classify]] | Rules classify the stored current snapshot | Implemented |
| Recurring risk areas | [[backend/services/observations.py#summaries]]; [[backend/services/observation_intelligence.py#metrics]]; [[backend/analytics/metrics.py#find_recurring_risks]] | Counts distinct inspections/themes and presents recurrence/group candidates | Implemented; recurring wording is not proof of a repeated regulatory violation |
| Mock observation dataset | [[data_engineering/observation_demo.py#records]]; [[backend/services/observations.py#run_batch]] | 72 synthetic fixture records available in code; current website defaults to real observations | Implemented, not the current default dataset |
| Category tagging | [[backend/services/observations.py#WorkspacePrediction]]; [[backend/analytics/observation_rubric.py]]; [[backend/genai/contracts.py#Classification]] | Legacy demo has detailed primary categories; newer contract uses broad category plus a more detailed theme | Implemented with different schemas; use the demo path for its detailed category breakdown |
| Severity tagging | Same prediction/contract modules; evidence validation | Low/Medium/High/Critical plus explicit abstention states | Implemented |
| Python | Backend, ETL and evaluation modules | Executes the backend and data services | Implemented |
| Claude Sonnet | [[backend/services/observations.py#claude_tag]]; [[backend/services/observations.py#run_batch]]; [[backend/genai/providers.py#ClaudeProvider]] | Optional adapter; demo batch requires a model ID containing `sonnet`, credentials and permitted AI execution | Partially satisfied operationally: implemented, not verified with a successful remote Sonnet run |
| pandas for tagging and aggregation | [[backend/services/observations.py#run_batch]]; [[backend/services/observations.py#summaries]] | Demo uses DataFrame, text `.map`, `.groupby`, `.agg`, `.explode`, `.nunique`; newer real-data APIs aggregate via SQL | Implemented in the demo path, not the active website's main aggregation engine |
| Synthetic data based on FDA 483 formats | [[data_engineering/observation_demo.py]] | Independently authored synthetic observations carry FDA format-reference URLs and source-locator text | Implemented as format-inspired fixtures; not authentic FDA findings or independently reviewed labels |
| Business Enablement / Regulatory Compliance | Product purpose, source evidence, review and traceability | Supports investigation and prioritization | Domain alignment; these labels are not proof of legal/regulatory certification |
| “Not Started” | Status shown in the supplied image | Source, UI, tests and stored runs already exist | Historical/planning status does not describe the current implementation; no external spreadsheet was edited |

## The exact path that most closely matches the image

```text
data_engineering/observation_demo.py : records()
  → 72 synthetic observations: 12 examples × 2 sites × 3 years
backend/services/observations.py : run_batch(provider, model, ...)
  → validates identities/text and builds a pandas DataFrame
  → frame['observation_text'].map(classify)
  → rules: tag_rules(text)
  → Claude: claude_tag(text, model, gate)
       → ClaudeProvider/request gate → Anthropic Messages request
       → WorkspacePrediction validation → validate(value, text)
  → persists run metadata and per-observation results
backend/services/observations.py : summaries(run_id)
  → pandas category/severity counts
  → explode themes → group by company/site/theme
  → distinct inspection counts → repeats = max(inspections - 1, 0)
backend/api/observation_workspace.py
  → reads run, rows, summaries, history; exports results; saves reviews
frontend/src/pages/ObservationWorkspace.jsx
  → retained older observation-workspace screen
```

This page is wired in `frontend/src/App.jsx` (removed legacy file), but the current [[frontend/src/main.jsx]] mounts [[frontend/src/experience/Experience.jsx]], not `App`. The newer Evidence workspace is [[frontend/src/reginsight/RegInsight.jsx]]. Therefore the presence of the old page in the repository is not proof that the default navigation exposes the image-matching demo workflow.

The `/api/observation-workspace/demo` endpoint runs the **rules** demo. It does not expose a Claude provider/model selector. The CLI [[data_engineering/tag_observations.py]] branches on `--dataset demo-legacy` and forwards provider/model options to `run_batch`; that is the implemented entry point for the strict Sonnet + pandas demo route. These details are important for a project demonstration.

## Why “Claude support” is not yet “Claude verified”

`run_batch` only accepts rules or claude. A Claude run requires a configured Sonnet model string and credentials. `claude_tag` makes a real provider request, validates JSON through `WorkspacePrediction`, checks source quotes and preserves provider/model/response metadata. A failed request creates failed rows and a `partial_failed` status; the strict legacy Claude path does not silently claim a rules result was generated by Claude.

The newer `Classifier` path has an explicit deterministic fallback and different provenance semantics. Keep these workflows separate when presenting them. Neither a mocked test nor a successful rules run demonstrates that a real Sonnet API request has succeeded. I did not read or disclose credentials and did not enable remote AI during this review.

## Verification performed for this review

Ran:

```powershell
.venv/Scripts/python.exe -m pytest tests/test_observation_workspace.py tests/test_intelligence_upgrade.py tests/test_website_workspace.py -q
```

**Result: 33 passed.** The relevant checks cover the 72-record synthetic rules batch, pandas category denominators, recurrence by distinct inspection, CSV export, invalid/negated observations, review history/concurrency, invalid evidence rejection, missing Claude credentials, mocked provider failure, normalized corpus ingestion and the website's scope/search/review behavior. Provider tests use controlled mocks; this result does not certify a live Claude integration.

See [[tests/test_observation_workspace.py#test_complete_batch_pandas_denominators_and_export]], [[tests/test_observation_workspace.py#test_claude_missing_credentials_is_not_success]], and [[tests/test_observation_workspace.py#test_provider_failure_keeps_failed_rows]].

## Gaps to close before claiming an exact end-to-end match

1. Expose or deliberately select the synthetic observation-demo workflow in the current UI. Merely retaining its older React component is insufficient for a default-screen demonstration.
2. Configure an authorized, available Sonnet model and run the synthetic batch through the strict Claude path. Preserve actual provider/model/response IDs, completed/failed counts and source-grounded outputs. This requires a separate authorized remote-provider execution, not a code-only assertion.
3. Show the pandas category/severity/recurrence summaries from that same run. The newer SQL dashboard is valid engineering, but it is not evidence that pandas generated those particular displayed results.
4. Present fixture provenance clearly: independently authored, FDA-format-inspired, synthetic data; expected labels are developer fixtures, not expert ground truth.

No missing feature was implemented in this review because the request was to check and explain the existing project.

## How to use the per-file function map

Open `RegInsight-Function-Connections.html`. Each file has its complete line extent, functions/classes/callbacks with exact start/end lines, parameter list, extracted return expressions and guards, outgoing call expressions, statically resolved destinations, incoming call references, and links into the numbered source atlas. Imports and imported-by files show module connections even when a method is selected at runtime.

Python functions are parsed with Python AST; JavaScript/JSX functions and callbacks are parsed with the project's Babel parser. Multiple compact JSX callbacks can occupy the same physical line; the map retains those true ranges rather than inventing new source line numbers. Calls that cannot be resolved statically are explicitly labeled; they are not guessed to be a particular service method. “No static caller found” can mean an API route, callback, entry point or dynamically invoked function—it does not prove unused code.

The documentation scope is the 143 indexed application/data/evaluation/test/configuration files in the existing atlas, not vendor dependencies, database rows, binary assets, secrets or every historical packaging/edit script. The manifest identifies the exact snapshot. The older walkthrough supplies the human explanation of page behavior and risk formulas alongside this more detailed symbol map.
