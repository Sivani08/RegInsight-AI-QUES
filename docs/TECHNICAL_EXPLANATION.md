# Technical review guide

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


| Question | Direct implementation |
|---|---|
| Where is the vector store? | backend/rag/repository.py:VectorRepository; data/workflows/vectors.db |
| What does it store? | Namespaced float32 BLOB vectors plus full Chunk JSON and indexed metadata |
| Where are document embeddings made? | VectorRepository.upsert_document -> EmbeddingService.embed |
| Where is the query embedded? | RetrievalService.search -> EmbeddingService.embed_query |
| Which model? | reginsight-hash-v1, 512-dimensional local lexical hashing; explicitly not neural |
| How are chunks made? | backend/rag/chunking.py:chunk_document; page/paragraph-aware 220/30 windows |
| What did a query retrieve? | GET /api/workflows/{id}/retrieval; actual IDs/text/scores/metadata/selected IDs |
| Why were they selected? | Metadata scope, descending exact cosine and configurable minimum score/top-k |
| How is relevance established? | Similarity is a candidate signal; development gold-source evaluation and SME inspection provide additional checks, not certainty |
| Which agent and why? | Stored RoutingDecision and matched rule IDs from routing.py |
| Multiple agents? | Analytics primary plus assessment secondary when both capabilities match; no recursive delegation |
| Judge implementation? | EvaluationService, workflow_judge.txt, strict eight-dimension JudgeOutput |
| Low score? | Bounded revision; exhaustion fails without publishing |
| Intermediate artifact? | Versioned inspection_evidence_assessment with citations, limits, risk and evaluation |
| Human gate? | AWAITING_HUMAN_REVIEW and finalize() checks both state and latest artifact approval |
| Approve/revise/reject? | POST /api/workflows/{id}/reviews/approve, revision or reject |
| Resume? | Approved content is published; revision reruns original specialist and judge; reject stops |
| Persistence? | WorkflowRepository saves typed state and event records atomically in SQLite |
| Auditability? | Query, explicit routing rubric, historical retrieval, drafts, evaluations, reviewers, revisions and timings |
| Services vs libraries? | Business decisions in Workflow/Retrieval/EvaluationService; transport and encoding in technical libraries |

Exact code snippets and function ranges follow in FILE_IMPLEMENTATION.md. Reproduce tests and inspect measured results in IMPLEMENTATION_REPORT.md. No model chain-of-thought is exposed.
