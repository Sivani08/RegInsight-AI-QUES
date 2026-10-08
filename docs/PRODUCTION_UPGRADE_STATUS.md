# Upgrade validation status

This upgrade is in progress. Do not interpret implemented components as a completed production acceptance test.

## Implemented

- Mandatory PostgreSQL application persistence with Alembic migrations; pgvector extension.
- Individual access-key accounts, expiring/revocable PostgreSQL sessions, analyst/reviewer/admin permissions.
- Named LangGraph stages with PostgreSQL checkpoints and persisted human review interrupts.
- APPROVE releases the approved artifact; MODIFY retains the original and reviewed replacement; REJECT requests bounded regeneration.
- PostgreSQL queue with atomic claims, expiring leases, heartbeat, bounded retries, idempotency checks and stale-worker fencing.
- Ollama `nomic-embed-text:latest` embeddings, verified model digest and 768 dimensions in local validation.
- Exact pgvector cosine retrieval, PostgreSQL full-text retrieval and reciprocal-rank hybrid search.
- Migration-only SQLite reader; application modules contain no SQLite runtime connection.

## Verified so far

- Unchanged baseline: 230 passed, 2 skipped after regenerating missing synthetic Parquet from supplied CSV.
- Fresh PostgreSQL database: eight targeted integration tests passed for queue concurrency/recovery, retries, persisted workflow resume, review decisions and user isolation. Generation and evaluation used explicit test doubles; embeddings and databases were real.
- Three-mode retrieval benchmark over 12 development queries and eight project references: keyword recall@5 0.2222, vector and hybrid recall@5 1.0; vector and hybrid MRR 1.0. This is a tiny development fixture, not independent domain validation.
- Search median timings in that run: keyword 2.75 ms, vector 6.15 ms, hybrid 7.51 ms. These exclude query embeddings and cannot predict large-corpus latency. See `production-retrieval-benchmark.json` for per-query embedding timings and model identity.

## Remaining acceptance work

- Finish PostgreSQL regression fixture migration and resolve full-suite failures.
- Validate actual process termination/restart, classification-job recovery and concurrent reviews.
- Validate historical data migration with row-level reconciliation and business metrics. Supplied delivery ZIP does not contain the complete real dataset.
- Expand retrieval negatives and independently review retrieval/abstention thresholds. Current 0.55 weak / 0.65 strong thresholds are provisional development settings; old hash-vector thresholds were inappropriate for semantic embeddings.
- Complete frontend build/browser checks and local real-model workflow validation.
- Complete deployment, operational, security, migration and architecture documentation; create and verify final portable ZIP.

No paid cloud provider was used for these checks. Docker deployment has not been run on this machine. Local native PostgreSQL was used instead. No MCP layer has been added.
