# Query-to-evidence trace

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


Endpoints:
- `GET /api/workflows/{id}/retrieval`: latest complete retrieval trace.
- `GET /api/workflows/{id}/trace`: query, routing, current and historical retrieval, tools, agents, artifacts, reviews, events and final response.
- `GET /api/workflows/{id}`: durable typed state.

Trace stores original query/request ID, null rewritten query, embedding model/version/dimensions, filters, top-k, policy thresholds, all returned candidates, similarity scores, document names, actual page/section/row metadata and exact final_chunk_ids. Each candidate keeps its full chunk payload. Candidate evidence is distinguished from chunks actually supplied to generation. Reranking scores are null because no reranker is used. Similarity is not labeled probability.

Retrieval history remains saved across human revisions; old artifacts do not lose their original evidence context. Selected observation run_id is resolved and frozen on the first request. Each artifact retains citations; D1 identifies a separate calculated analytical result with its existing analysis_id. No generated analysis is inserted into the source index.

In the existing evidence section, expand AI assessment and workflow review, then Retrieved evidence. Used-in-context labels distinguish selected chunks from other candidates. Complete operational trace opens in the browser as JSON. This exposes operational decisions and scores, not private model chain-of-thought.
