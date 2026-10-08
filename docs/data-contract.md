# Importing inspection records

Each input row must represent one inspection. Map real source columns in a copy of `config/schema_mapping.yaml`; remove mappings for absent columns. Unmapped canonical names are recognized directly. At least one mapped company, site or FEI identity is required. The original file should be retained by its owner; quarantined rows preserve the source column values and row number.

Supported inputs: CSV (UTF-8), Excel XLSX, and Parquet. XLS is supported after installing the optional `xlrd` package. CSV uses strict parser error handling. Ambiguous day/month dates are not guessed: supported patterns are ISO `yyyy-MM-dd`, US `MM/dd/yyyy`, and ISO midnight timestamps. Extend the format list deliberately for other source conventions.

Classification accepts NAI, VAI, OAI, and their full names. Unknown values are retained in `raw_classification` while canonical classification is null. Blank observation text is not replaced with invented content. Known zero observation counts are distinct from missing counts. Citation flags accept yes/no, true/false, y/n and 1/0; all other values remain null. Fiscal year is preserved as supplied rather than inferred from calendar year.

Missing optional fields do not reject a record. Invalid nonempty dates, future dates relative to the chosen reference date, invalid/negative counts, or completely missing identity do reject it. Repeated inspection IDs retain the first source row and quarantine subsequent rows. This includes conflicting duplicates, which require human review. Absent IDs become deterministic SHA-256 identifiers derived from canonical source values; they are labeled DERIVED and are not FDA identifiers.

The quality reconciliation is:

`total = valid + rejected + duplicate`

Duplicates are a separate category, including duplicate rows that also contain invalid values. Missing-value counts refer to all input rows after normalization; completeness includes all 14 canonical fields, including optional fields. Unknown classifications and invalid dates can overlap missing-value counts; these are diagnostics, not additive categories.

## Replacing demonstration data

1. Copy the mapping file and set its source column names.
2. Run ETL into a new processed directory and review its quality report and quarantine files.
3. Load that processed directory into the application database. The database loader replaces the current dataset in one transaction.
4. Restart or refresh the application. Dataset labeling comes from the imported quality metadata. Do not use `--synthetic` for real data.

No file uploads or automatic downloads are needed. Dataset ingestion is an explicit operator CLI action. This prototype handles one active dataset at a time.
