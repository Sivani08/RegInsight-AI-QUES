# Chunk schema and provenance

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


Actual Pydantic model: `backend/workflows/schemas.py:Chunk`.

| Field | Meaning |
|---|---|
| chunk_id | CHK- plus SHA-256-derived stable identity incorporating source, chunk position, content and embedding space |
| document_id | Stable supplied source identifier or content-derived ID |
| document_name | Actual file/reference name |
| source_type | project_reference, observation, pdf, pptx or text |
| domain | Routing/retrieval category, not regulatory approval |
| section | Source section/slide locator when supplied; otherwise null |
| page_number | Actual PDF page if available; otherwise null |
| chunk_index | Zero-based sequence within the indexed document unit |
| chunk_text | Preserved extracted text segment |
| token_count | Regex nonwhitespace token units; not model-tokenizer count |
| token_count_method | regex_nonwhitespace_v1 |
| metadata | Available source file/row/sheet, dataset, snapshot, observation/inspection IDs, source assessment or reference locator |
| created_at | UTC indexing time |
| embedding_model / embedding_version | Actual lexical model and preprocessing version |

No study, patient, drug, product, regulator approval or document access role is fabricated. There is no per-document ACL layer; existing local/shared-key application access controls apply. Vector records keep metadata; operational logs avoid dumping evidence text. The persisted workflow trace intentionally retains evidence for audit, so deployments need filesystem protection and retention policy.

Chunk boundaries and limitations: `RAG_ARCHITECTURE.md`. Source population: `WorkflowService.selected_observation()`, `RetrievalService.seed_references()`, `scripts/index_workflow_sources.py:documents()`.
