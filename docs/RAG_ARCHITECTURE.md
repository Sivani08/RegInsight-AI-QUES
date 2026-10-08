# RAG architecture

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


## Ingestion
`scripts/index_workflow_sources.py` handles PDF pages (pypdf), PPTX slide XML, TXT and Markdown. It also seeds the existing curated project references. Selected observations are indexed on explicit workflow submission through WorkflowService using the existing snapshot tags service. It never automatically embeds the full inspection corpus.

```
Source -> page/slide/observation extraction -> paragraph-aware bounded chunks
       -> EmbeddingService -> SQLite BLOB vectors + complete chunk metadata
Query -> same EmbeddingService -> exact cosine SQL search -> filtered candidates
      -> top-k above weak threshold -> persisted trace -> generation context
```

Chunk defaults: 220 whitespace-token units, overlap 30 only when a paragraph exceeds the limit. Paragraph boundaries remain separate; PDF page/slide/observation boundaries are never crossed. Extracted newlines are preserved. A very long paragraph can split a sentence or extracted table; no OCR or table reconstruction is claimed. Actual model tokenizer counts are not claimed.

Default embedding: `reginsight-hash-v1`, preprocessing version `1.1:word-bigram-signed-l2`, 512 dimensions. Lowercase alphanumeric tokens, stopword removal, unigram+bigram features, SHA-256 signed hashing, L2 normalization. This is lexical embedding, not learned semantic embedding. It requires no API, model download, retry or rate limit. Collisions and paraphrase misses are known limitations.

Search defaults: 20 candidates, final top 5; STRONG_HIT >= 0.35, WEAK_HIT >= 0.12, otherwise MISS. These configurable cosine policy cutoffs are prototype values, not calibrated confidence probabilities. Weak hits require review; misses with no SQL evidence abstain. A SQL-backed query may proceed using D1 despite no vector hit. There is no query rewrite, reranking model, or fusion algorithm; corresponding trace fields are null.

The development evaluation records source precision/recall and examples, including false positives. A production rollout needs a held-out labeled corpus and a suitable neural model if paraphrase recall matters. The implementation deliberately does not disguise lexical similarity as neural semantics.

The existing chatbot and legacy grouping remain intact; they are different entry points. New path: `/api/workflows` or the existing evidence panel's expanded workflow section.
