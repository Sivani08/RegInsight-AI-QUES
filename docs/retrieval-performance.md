# Retrieval and evaluation update

The application now uses a bounded in-process L1 cache with single-flight request coalescing, a versioned narrow analytics projection, covering indexes, precomputed observation summaries, and trigram search where SQLite supports it. The canonical inspection and observation data remain the evidence source. Cache keys include dataset identity, filters, query plan, and observation run/review revision, so a dataset replacement or review change cannot reuse stale results.

The browser uses a 32-entry, 8 MB, 15-second GET cache and deduplicates concurrent requests. Mutations, authentication changes, failed responses, and aborted callers do not populate it. Responses include a `Server-Timing` header for local profiling.

The benchmark is a small local smoke measurement: three sequential requests per route, with first and warm samples shown separately. It is not a production capacity guarantee. On the supplied machine, warm medians changed as follows:

| Route | Before | After |
| --- | ---: | ---: |
| Dashboard | 2,578 ms | 77 ms |
| Year dashboard | 1,923 ms | 54 ms |
| Ranked copilot | 2,179 ms | 31 ms |
| Observation summary | 9,474 ms | 23 ms |
| Observation page | 394 ms | 43 ms |
| Observation search | 5,044 ms | 40 ms |

The first request can still be slower while a cache or SQLite index warms. The live workload should be profiled again with representative concurrency before deployment.

## DeepEval

`requirements-eval.txt` pins DeepEval 4.2.6 in a separate evaluation environment. `evaluation/metrics.py` uses DeepEval's custom `BaseMetric` interface for numeric agreement, retrieval precision/recall, evidence grounding, scope correctness, and latency budgets. `scripts/collect_evaluation.py` gets live responses but derives expected counts, IDs, and source fields independently from the canonical SQLite tables. `evaluation/run.py` runs the actual DeepEval evaluator offline with telemetry and dotenv loading disabled, and includes negative controls that must fail when numbers, scope, evidence, or latency are deliberately corrupted.

This is a deterministic contract evaluation. It does not claim subjective LLM answer quality and makes no external judge or Confident AI upload.
