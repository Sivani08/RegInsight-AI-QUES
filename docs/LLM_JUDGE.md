# LLM-as-a-Judge

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


`backend/workflows/evaluation.py:EvaluationService.evaluate()` makes a separate real local Ollama call through `backend/libraries/structured_llm.py`. This is not the earlier deterministic DeepEval metric and not a fabricated fixture score.

Prompt: `config/prompts/workflow_judge.txt`. Inputs: original query, generated draft, citation IDs, retrieved source text/metadata and calculated tool results. Schema: JudgeOutput with eight bounded 0-10 dimensions, concrete issues and brief rationale. The judge does not receive authority to approve the workflow.

Dimensions: relevance, groundedness, factual consistency, completeness, domain correctness, safety, evidence coverage, clarity. Anchors: 0 absent/contradictory; 3 major errors; 5 material gaps; 7 mostly supported; 9 supported; 10 supported and exceptionally clear.

Overall score is recomputed in Python as the equal-weight mean * 10. PASS requires >=80 AND groundedness>=7 AND safety>=7. Scores >=60 that do not pass require revision; lower scores FAIL. Both unsuccessful decisions enter the bounded revision loop; exhausted iterations stop with FAILED and no final assessment. Default maximum total generation iterations is 3, shared by automated and human revisions.

High/critical risk and explicit/weak-evidence review requirements cannot be bypassed by a high judge score. Judge failure, malformed JSON, timeout or unavailable model fail explicitly. No fallback fake judge is used.

Generation and judging default to `reginsight-chat:qwen3-1.7b`, temperature 0. This is separate-role judging with the SAME base model, not independent model verification. Correlated errors and self-evaluation bias remain; same_model is persisted and displayed. WORKFLOW_JUDGE_MODEL can select another downloaded local model. No extra multi-judge ensemble is added to every prototype request.

Tests using FakeLLM are labeled simulations. `live-workflow-demo.json` records actual model calls, scores, latency and an automated demonstration approval (not an SME approval).
