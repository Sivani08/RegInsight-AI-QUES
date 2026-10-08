# Delivery notes

The distributable archive contains the application source, configuration, documentation, frontend build, tests, evaluation cases, and source knowledge files.

Large generated runtime artifacts are intentionally omitted from the archive to keep it usable for transfer:

- `data/inspections.db`
- `data/intelligence/intelligence.db*`
- generated Parquet files under `data/real/` and `data/processed/`
- dependency caches and Python/pytest caches

These artifacts are derived data. Recreate the local inspection and intelligence stores with the project setup and data processing scripts, and populate the vector store by running `scripts/index_workflow_sources.py` against the source documents. The application code and schema remain in the archive.
