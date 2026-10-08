# End-to-end execution trace

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


**Evidence type:** actual local Ollama calls plus real SQLite retrieval. The approval actor below is explicitly automated for the demonstration, not an SME.

Query: Explain regulatory significance of OAI VAI NAI inspection outcome classifications.

Workflow: `a03c5069-9430-4833-a859-ec2ae81ee8ea`

Agent: InspectionAssessmentAgent

Routing reason: Observation, finding, CAPA, quality/compliance, inspection interpretation -> InspectionAssessmentAgent. Recommendations, compliance approval, release decisions, safety or critical impact -> mandatory review. Explicit user review request or weak retrieval -> mandatory review.

Risk: HIGH

Retrieval: WEAK_HIT

Embedding: reginsight-hash-v1 / 1.1:word-bigram-signed-l2

| Rank | Chunk | Document | Cosine | In context |
|---|---|---|---:|---|
| 1 | CHK-ce6321c7c1b5f98298ba407df50dc7c8 | Inspection classifications | 0.168540 | True |
| 2 | CHK-8b5aba5ee5fc70cd77c92c4abada1621 | RegInsight purpose and chatbot | 0.118345 | False |
| 3 | CHK-9b1571a961cef014e5175ad16f759175 | Local operation, latency and evaluation | 0.022559 | False |
| 4 | CHK-7ad2cb92280339559557f80bb5300a58 | Real and synthetic datasets | 0.000000 | False |
| 5 | CHK-e8694b9c0347efa1f0e7a3d1402d3d9d | Risk scores and interpretation | 0.000000 | False |
| 6 | CHK-526ac0023d3e8afb716dad05e21b27c3 | Cleaning and evidence provenance | -0.022222 | False |
| 7 | CHK-46d5762458748c5b7c05364b9415018a | Observation themes and severity | -0.045466 | False |
| 8 | CHK-7d2e94e5fda4558e5066c49787b2fa55 | Recurring risk methodology | -0.094676 | False |

## Actual draft

The OAI (Official Action Indicated) classification in FDA inspections represents a recommendation for regulatory or administrative action, not a mandatory requirement. This classification is derived from inspection outcomes and is used to guide agencies in their decision-making processes. The classification system includes NAI (No Action Indicated) and VAI (Voluntary Action Indicated), with OAI being the highest level of recommendation. The classification is not based on the percentage of observations but rather on the specific findings during inspections.

## Actual evaluation

```json
{
  "model": "reginsight-chat:qwen3-1.7b",
  "generation_model": "reginsight-chat:qwen3-1.7b",
  "same_model": true,
  "overall_score": 91.25,
  "decision": "PASS",
  "dimensions": {
    "relevance": 9.0,
    "groundedness": 9.0,
    "factual_consistency": 9.0,
    "completeness": 9.0,
    "domain_correctness": 9.0,
    "safety": 10.0,
    "evidence_coverage": 9.0,
    "clarity": 9.0
  },
  "issues": [],
  "rationale": "The query asks for an explanation of the regulatory significance of OAI VAI NAI inspection outcome classifications. The draft provides a clear and accurate description of the classifications, their meanings, and their regulatory context. The evidence supports the claims with specific definitions and references to the FDA's documentation. The tool results are empty but do not affect the validity of the information provided. The explanation is concise, complete, and free of unsupported claims or limitations.",
  "rubric_version": "1.0",
  "thresholds": {
    "pass": 80.0,
    "revision": 60.0,
    "minimum_groundedness": 7.0,
    "minimum_safety": 7.0
  },
  "evaluated_at": "2026-10-07T07:03:36.583505+00:00"
}
```

State before approval: **AWAITING_HUMAN_REVIEW**; final_response: `None`.

After the labeled automated demo approval: **COMPLETED**. Published content equals the approved artifact; no post-approval model call.

## Model call evidence

```json
[
  {
    "purpose": "generation:InspectionAssessmentAgent",
    "model": "reginsight-chat:qwen3-1.7b",
    "latency_ms": 21281,
    "output_tokens": 179,
    "prompt_tokens": 502
  },
  {
    "purpose": "judge",
    "model": "reginsight-chat:qwen3-1.7b",
    "latency_ms": 23406,
    "output_tokens": 177,
    "prompt_tokens": 648
  }
]
```
Full source text, artifacts, citations, events and decisions: `live-workflow-demo.json`. No private model reasoning is recorded.