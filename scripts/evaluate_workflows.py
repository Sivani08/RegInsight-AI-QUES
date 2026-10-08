"""Actual deterministic routing/retrieval evaluation; never invents judge metrics."""
import sys,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.workflows.policy import load_policy
from backend.workflows.schemas import WorkflowRequest
from backend.workflows.routing import route
from backend.rag.embeddings import EmbeddingService
from backend.rag.repository import VectorRepository
from backend.rag.service import RetrievalService

def run():
    payload=json.loads((ROOT/'evaluation/workflow_cases.json').read_text());p=load_policy();rows=[]
    r=RetrievalService(VectorRepository(embedding=EmbeddingService(p.embedding_dimensions,p.embedding_model)),p)
    r.seed_references(ROOT)
    for case in payload['cases']:
        analysis,decision=route(WorkflowRequest(question=case['query']),p)
        trace=r.search(case['query'],case['id'])
        selected={x.chunk.document_id for x in trace.results if x.chunk.chunk_id in trace.final_chunk_ids}
        gold=set(case['expected_sources']);matched=selected&gold
        row={'id':case['id'],'query':case['query'],'expected_agent':case['expected_agent'],'actual_agent':decision.selected_agent,
            'routing_correct':decision.selected_agent==case['expected_agent'],'risk_correct':analysis.risk_level==case['risk_level'],
            'retrieval_status':trace.retrieval_status,'retrieved_documents':sorted(selected),
            'precision':len(matched)/len(selected) if gold and selected else 0 if gold else None,
            'recall':len(matched)/len(gold) if gold else None,'top_scores':[(x.chunk.document_id,x.similarity_score) for x in trace.results[:3]],
            'mandatory_review_policy':analysis.requires_hitl,'judge_score':None,
            'expected_behavior':case['expected_behavior']}
        rows.append(row)
    agent_stats=[]
    for agent in sorted({r['expected_agent'] for r in rows}):
        group=[r for r in rows if r['expected_agent']==agent]
        scored=[r for r in group if r['precision'] is not None]
        agent_stats.append({'agent':agent,'test_queries':len(group),'routing_accuracy':sum(x['routing_correct'] for x in group)/len(group),
            'retrieval_precision':sum(x['precision'] for x in scored)/len(scored) if scored else None,
            'retrieval_recall':sum(x['recall'] for x in scored)/len(scored) if scored else None,'judge_score':None})
    result={'scope':payload['scope'],'method':'Actual local vector search; document-level precision/recall; no LLM calls',
        'routing_accuracy':sum(r['routing_correct'] for r in rows)/len(rows),'agents':agent_stats,'cases':rows,
        'unmeasured':['semantic faithfulness','human acceptance rate','production hallucination rate','held-out judge calibration']}
    target=ROOT/'docs/workflow-evaluation-results.json';target.parent.mkdir(exist_ok=True);target.write_text(json.dumps(result,indent=2))
    print(json.dumps({'routing_accuracy':result['routing_accuracy'],'agents':agent_stats},indent=2))
if __name__=='__main__':run()
