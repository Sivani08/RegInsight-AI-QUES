"""Measure the same development queries against keyword, vector and hybrid retrieval.

Uses the configured PostgreSQL corpus and local embeddings. No hosted LLM calls.
This small fixture is not a held-out regulatory quality evaluation.
"""
import json
import time
import statistics
from pathlib import Path
from backend.workflows.policy import load_policy, ROOT
from backend.rag.embeddings import EmbeddingService
from backend.rag.repository import VectorRepository


def main():
    policy=load_policy()
    embedding=EmbeddingService(policy.embedding_dimensions,policy.embedding_model)
    repository=VectorRepository(embedding=embedding)
    cases=json.loads((ROOT/'evaluation/workflow_cases.json').read_text())['cases']
    rows=[]
    for case in cases:
        started=time.perf_counter()
        vector=embedding.embed_query(case['query'])
        embedding_ms=(time.perf_counter()-started)*1000
        for mode in ('keyword','vector','hybrid'):
            durations=[]
            for _ in range(3):
                start=time.perf_counter()
                results=repository.search(vector if mode!='keyword' else None,{},policy.retrieval_candidate_limit,query=case['query'],mode=mode)
                durations.append((time.perf_counter()-start)*1000)
            documents=list(dict.fromkeys(row.chunk.document_id for row in results))[:policy.retrieval_top_k]
            gold=set(case['expected_sources'])
            matches=gold.intersection(documents)
            rank=next((i+1 for i,identifier in enumerate(documents) if identifier in gold),None)
            rows.append({'case':case['id'],'mode':mode,'expected_documents':sorted(gold),'documents':documents,
                'recall_at_5':len(matches)/len(gold) if gold else None,
                'precision_at_5':len(matches)/len(documents) if gold and documents else 0 if gold else None,
                'reciprocal_rank':1/rank if rank else 0 if gold else None,
                'search_median_ms':round(statistics.median(durations),2),
                'query_embedding_ms':round(embedding_ms,2) if mode!='keyword' else 0,
                'top_cosine':max((row.similarity_score for row in results),default=0),
                'expected_behavior':case['expected_behavior']})
    summaries=[]
    for mode in ('keyword','vector','hybrid'):
        selected=[row for row in rows if row['mode']==mode]
        scored=[row for row in selected if row['recall_at_5'] is not None]
        summaries.append({'mode':mode,**{key:round(statistics.mean(row[key] for row in scored),4) for key in ('recall_at_5','precision_at_5','reciprocal_rank')},
            'median_search_ms':round(statistics.median(row['search_median_ms'] for row in selected),2)})
    report={'scope':'12 development queries, curated project references; not held-out or SME-labelled; latency is local and corpus-specific.',
        'model':embedding.model,'model_digest':embedding.version,'dimensions':embedding.dimensions,
        'corpus_chunks':repository.count(),'repeats':3,'summaries':summaries,'cases':rows,
        'limitations':['No human acceptance or hallucination claim','Exact pgvector search; no large-corpus load test','Query embedding measured once per query; search timings exclude embedding']}
    target=ROOT/'docs/production-retrieval-benchmark.json'
    target.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'summaries':summaries,'report':str(target)},indent=2))


if __name__=='__main__':
    main()
