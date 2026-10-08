# Observation workflow: requirement closure and demonstration

This release adds a separate, explicitly synthetic Observation Workspace. It contains 72 individually identified observations across six fictional inspections, two sites and three years. It does not merge synthetic findings into the real portfolio.

## What is implemented

- Complete persisted observation-level tagging: IDs, text, source references, prediction, category, multiple themes, severity, quotes, provider/model, rubric version and review state.
- pandas DataFrame tagging input, category/severity groupby summaries, exploded multi-theme aggregation, distinct inspection recurrence, CSV and JSON exports.
- Six substantive categories plus Unclassified: records/data integrity, laboratory controls, quality management, production/validation, personnel/training, and facilities/equipment.
- Low, Medium, High, Critical and Insufficient evidence. The application rubric is a review-priority interpretation, not an FDA severity system. Confidence is unavailable for rules and uncalibrated when supplied by Claude.
- Explicit Claude Sonnet batch execution with validated labels and exact evidence quotations. Errors remain failed rows; a Claude failure never becomes a successful rules run. Repeated identical texts share a result within a run; each source observation remains independently identified.
- Review correction UI, immutable original predictions, append-only reviewer/rationale audit and optimistic version checks. Review identity is self-declared; no production authentication is claimed.
- Evaluation of predictions against the reviewed subset: category/severity agreement and micro theme precision/recall. Until humans review, these remain unavailable. Developer-authored fixture labels are never represented as expert ground truth.

## Public format provenance

Reviewed 2026-09-15:

1. [Public FDA Form 483 example](https://www.fda.gov/about-fda/montana-compounding-pharmacy-pc-missoula-mt-483-issued-09202016), pages 1-3: firm identification, inspection dates, FEI, numbered observations, detail under observations and repeat-observation structure.
2. [FDA Form 483 FAQ](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-references/fda-form-483-frequently-asked-questions): observations are not a final agency determination.
3. [Inspection observations](https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/inspection-references/inspection-observations): annual citation summaries are a different data grain.

Mapping: public firm/date/identity fields become fictional company_name, inspection_date and DEMO inspection IDs; numbered observations become observation_number and stable observation_id; detailed narratives become independently authored fictional observation_text. Every example records format_source_url, source_locator and template_id. No finding, company, FEI or severity label from the public example is attributed to the synthetic firms. This is a tabular format adaptation, not a reproduction of an official form. No empirical representativeness claim is made: the 12 narratives are repeated to test recurrence across sites/years.

## Run from project root

Use your installed environment, or the prepared local interpreter at ../../work/.venv/Scripts/python.exe.

```powershell
python -m data_engineering.tag_observations --provider rules --output data/observations/latest
```

For Claude, securely configure ANTHROPIC_API_KEY (AI_API_KEY is also supported), and set AI_MODEL to a Sonnet model ID available to your account. Consult [Anthropic model IDs](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions). Do not paste or commit credentials.

```powershell
python -m data_engineering.tag_observations --provider claude --model $env:AI_MODEL --output data/observations/claude
```

The run returns nonzero on missing settings or failed rows. Inspect run-report.json for provider/model, full completion, failed count and source hash; inspect tagged-observations.json for supporting quotes and response IDs. Never use a rules report as evidence of Sonnet execution.

## Demonstrate end to end

1. Start the application and open Observation Workspace. Its synthetic-data banner is independent of the portfolio banner.
2. Inspect the completed run: 72 source rows, 72 tagged rows, rules provider.
3. Read one original observation, its tags and quotations; open the public format reference.
4. Check pandas summaries. Primary category totals reconcile to tagged observations. Theme totals overlap. Recurrence counts distinct inspections, not words or duplicate themes.
5. Review/correct a record, supply exact evidence and a rationale, and save. Inspect review history and updated metrics. Do not enter fabricated expert reviews merely to populate a chart.
6. Run Claude using the command above when credentials are available. Refresh the workspace to inspect the new run and compare results.
7. Export run outputs. Confirm that source text and original model predictions survived review.

## Acceptance status

Software implementation is complete for this bounded synthetic workflow. Live Claude execution remains pending because no API credential was available during development. Domain-expert validation remains pending because no independent expert labels were supplied. The reviewer interface and evaluation machinery are implemented; an actual expert assessment cannot be generated by software development alone. Existing real-portfolio recurrence performance limitations remain outside this synthetic workflow.
