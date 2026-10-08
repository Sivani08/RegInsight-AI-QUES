# Evaluation framework

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


Existing `evaluation/run.py` DeepEval custom deterministic contracts remain unchanged. New `scripts/evaluate_workflows.py` measures real routing decisions and exact vector retrieval against `evaluation/workflow_cases.json`.

Run:
```
python scripts/evaluate_workflows.py
python -m pytest tests/test_workflows.py -q
```

The new development dataset has 12 cases spanning reference explanation, inspection interpretation, analytics, mandatory review, unrelated retrieval and unsupported patient advice. Document-level precision/recall use selected document IDs against explicit expected_sources. Cases without a labeled source target have null precision/recall. Results are saved in workflow-evaluation-results.json with per-agent sample counts, routing accuracy, actual top scores and unmeasured metrics.

This is a small development smoke set, not an independent held-out benchmark. No production faithfulness, hallucination rate, safety sensitivity or human acceptance percentage is asserted. Judge scores for this deterministic suite are null. Real judge results are separately evidenced by the live demonstration.

Tests cover query routing, multi-agent selection, schema rejection, embeddings, chunk metadata and overlap, exact vector persistence/filtering, strong/weak/miss policy, judge thresholds, mandatory gates, stale versions, revision limits, rejection, exact-content publication, repository concurrency, process reconstruction and API integration. Provider-boundary test doubles are explicit; real SQLite/vector operations remain active.

See IMPLEMENTATION_REPORT.md for actual final test counts and live/browser results. A production evaluation should add labeled paraphrases, adversarial source instructions, domain SME ratings and a separate-model judge comparison.
