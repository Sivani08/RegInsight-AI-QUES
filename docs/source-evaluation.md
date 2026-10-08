# Supplied-source evaluation and integration

## Fit to the project brief

The screenshot describes an insight-generation project: classify inspection observations by category and severity and identify recurring risk areas, using Python, Claude Sonnet and pandas. The current prototype meets that core workflow through its observation analyzer, category/theme taxonomy, recurrence analysis and optional Claude adapter. Its Spark ETL, deterministic risk engine, tool-based agent, React interface and evidence snapshots extend the brief.

The screenshot's “Not Started” value is a catalogue status, not an instruction to reset this repository. Workbook text and footnotes were treated as evidence and definitions, never as execution instructions.

## Verified source inventory

| File | Actual data grain | Nonblank data rows | Role |
| --- | --- | ---: | --- |
| e4832250-43dc-4c0c-982b-b31f87205869.xlsx | Inspection / project-area result | 341,046 | Inspection history and classifications |
| e00adefd-b9ce-414f-ae04-21c950fb5f27.xlsx | Posted citation attached to an inspection | 280,130 | Observation text and CFR evidence |
| Inspection_Observations_FY23_0.xlsx | Fiscal-year / program / citation frequency | 1,546 | FY2023 industry benchmark |
| inspection_observations_fy24.xlsx | Fiscal-year / program / citation frequency | 1,544 | FY2024 industry benchmark |
| inspection_observations_fiscal_year_2025_0.xlsx | Fiscal-year / program / citation frequency | 1,606 | FY2025 industry benchmark |

Counts exclude headers and blank/formatted-only rows. In FY2023, several worksheet dimensions extend to row 16,384, but most rows contain no data. Using max_row as the record count would substantially overstate the dataset.

Workbook originals were read only and remain unchanged. Filenames, sheet names, source row numbers and SHA-256 hashes are preserved in data/real/source_evaluation.json and source evidence.

## Inspection identity and join

* 341,046 source rows represent **274,886 distinct inspection IDs**.
* The additional **66,160 project rows** are preserved inside the corresponding inspection's source evidence.
* **133,375 distinct FEIs** appear.
* Dates span **2008-10-01 to 2026-08-24**.
* No inspection ID had conflicting FEIs or inspection end dates.
* **15,929 inspection IDs** have more than one project-level classification.
* All **280,130 citation rows** match on inspection ID + FEI + end date, covering **76,162 distinct inspections**.
* No unmatched citations or exact duplicate citation rows were found in that join audit.

For inspection-level prioritization, classification is explicitly defined as the worst recorded project classification: OAI > VAI > NAI. This gives **169,180 NAI**, **94,467 VAI**, and **11,239 OAI** inspection-level rollups. These are derived rollups, not a replacement for the original project-level FDA classifications; every component classification remains visible in evidence.

Site labels are derived from FEI and source city because a separate site-name column is absent. Company groups use normalized source legal names. The 119,332 legal-name groups are not a corporate-parent hierarchy; aliases, acquisitions and historical renamings have not been resolved.

## Missing-data rules

“Posted Citations” measures publication, not proof that an inspection had or lacked deficiencies. In this export, its distinct-inspection positive count equals the joined citation population (76,162), but a negative posting flag is not interpreted as a clean inspection.

True citation flags and total observation counts are not provided. The real-data adapter leaves those canonical fields null, retaining posted-citation indicators and available citation-row counts separately. Consequently, citation-history, negative-citation-trend and observation-count burden components are unavailable in real-data risk scores. Available components are normalized with an explicit coverage percentage. Scores are not directly comparable with the synthetic demonstration's more complete scores.

Citation text is linked only to its verified inspection. Missing citation text remains unavailable. No annual frequency or template observation was attached to a company.

## Annual benchmarks

| Fiscal year | Citation-frequency sum | Unique Forms 483 recorded in the source system |
| --- | ---: | ---: |
| 2023 | 13,012 | 4,428 |
| 2024 | 13,009 | 4,056 |
| 2025 | 15,265 | 4,862 |

These are different measures. Frequency sums count citation occurrences across categories. The unique form totals come from Summary!F18 for FY2023 and Summary!B14 for FY2024/FY2025. The source footnotes say program totals can count a form more than once, and that some manually prepared forms are omitted.

The annual view supports fiscal year, program, text/CFR search and frequency-weighted theme tagging. Theme matches can overlap and must not be added as if mutually exclusive. It retains the published template text, including placeholders such as “Specifically, ***”; it does not present these templates as site-specific findings.

## Implementation changes

* Added read-only source audit and reproducible relational importer.
* Preserved all project rows and citation join evidence in canonical records.
* Produced canonical Parquet, an independent real-data SQLite database, annual benchmark Parquet/JSON and an audit manifest.
* Materialized all site/company summaries for the larger dataset. Dashboard totals use the whole population; ranking tables show bounded results.
* Added search-backed company lookup, SQL inspection pagination and lightweight analytics queries.
* Added a separate Annual Benchmarks page with source references and correct denominators.
* Kept synthetic and real data in separate databases.
* Large unscoped agent investigations return a request to select a company/site rather than creating an enormous evidence snapshot. Company comparison and priority rankings remain available. Portfolio-wide analytics remain in Dashboard/Trends; annual aggregates remain in Annual Benchmarks.
* Global alerts on large datasets review the 20 highest-ranked sites, explicitly labeled in the UI. Scoped company alerts inspect that company's sites.

## Reproduce

From the repository root, with the Python environment installed:

```powershell
.venv\Scripts\python.exe -m data_engineering.source_review --source-dir "PATH_TO_WORKBOOKS" --staging "work/new_source_review.sqlite" --report "work/new_source_review.json"
.venv\Scripts\python.exe -m data_engineering.fda_source_adapter --staging "work/new_source_review.sqlite" --review "work/new_source_review.json" --output data/real
.venv\Scripts\python.exe -m backend.services.mart --database data/real/inspections.db
.\start-real.ps1
```

The audit script expects the five supplied filenames. Use a new staging path to preserve previous staging databases. The importer explicitly replaces the target real-data database; retain a backup when importing a different snapshot. Do not import concurrently with application requests.

The real-data adapter executed here uses Python/SQLite and Arrow for the multi-grain join. The original generic PySpark ETL remains available and was previously executed/tested on synthetic data. Do not describe the real-data join as a completed Spark execution. A dedicated Spark validation/enrichment job is provided for the prepared canonical Parquet; its execution status is reported separately.

Changing risk weights requires rebuilding materialized summaries. Paid Claude/OpenAI inference remains optional and was not live-tested.

## Executed validation

The independent PySpark validation/enrichment job completed successfully against all prepared real records: 274,886 rows and distinct inspection IDs, 341,046 retained project rows and 280,130 linked citation rows. Its report is data/real/spark_validation.json. The multi-grain source join itself remains the Python/SQLite/Arrow adapter described above.
