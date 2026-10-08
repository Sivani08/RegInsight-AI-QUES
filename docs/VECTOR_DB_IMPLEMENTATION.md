# Vector database implementation

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


Technology: embedded SQLite exact vector store, not pgvector/FAISS/Chroma or an ANN server. `backend/rag/repository.py:VectorRepository` owns storage and search in `data/workflows/vectors.db` (or WORKFLOW_DATA_DIR).

`vector_chunks`: space, chunk_id, document_id, domain, dataset, source_type, vector BLOB, payload JSON. Primary key `(space,chunk_id)`. A metadata index covers `(space,document_id,domain,dataset,source_type)`.

`embedding_cache`: space, SHA-256 text hash, packed float32 vector; key `(space,hash)`. Space includes model, preprocessing version and dimensionality. Changed preprocessing cannot silently reuse old vectors. Documents are replaced atomically within their namespace; stale chunks are deleted. Capacity defaults to 25,000 chunks. Do not treat this exact-scan prototype as a large-scale ANN service.

SQLite registers deterministic `cosine_similarity(vector, query_blob)` backed by validated Python arithmetic. Query SQL filters by namespace and allowed metadata fields before sorting by score descending with chunk ID tie-breaking. Query parameters are bound; filter identifiers are allowlisted. Search returns native structured chunk metadata, rank and score. Cache/query vectors are local; no external embedding calls.

```
SELECT payload, cosine_similarity(vector, ?) score
FROM vector_chunks WHERE space=? AND <allowlisted metadata predicates>
ORDER BY score DESC, chunk_id LIMIT ?
```

Document chunks are embedded during `upsert_document()` in bounded batches; query vectors are computed by `RetrievalService.search()`. Exact vector comparisons are O(filtered chunks * dimensions). Index capacity and CPU latency should be measured before increasing scope. Existing SQLite observation-group assignments are not repurposed or renamed as the new vector index.
