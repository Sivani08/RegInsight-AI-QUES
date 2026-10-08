"""Isolated real PostgreSQL/vector tests with an explicitly simulated LLM boundary."""
import json,math,uuid
import pytest
from backend.workflows.policy import Policy
from backend.workflows.schemas import WorkflowRequest,ReviewDecision,JudgeOutput,GeneratedDraft
from backend.workflows.routing import route
from backend.workflows.repository import WorkflowRepository,Conflict
from backend.workflows.service import WorkflowService
from backend.workflows.evaluation import EvaluationService
from backend.rag.embeddings import EmbeddingService
from backend.rag.repository import VectorRepository
from backend.rag.service import RetrievalService
from backend.rag.chunking import chunk_document

class FakeLLM:
    """Test double only. Tests never present these scores as live model evidence."""
    def __init__(self,scores=None):self.calls=[];self.scores=list(scores or [9]);self.fail=False
    def generate(self,model,system,payload,schema,purpose):
        self.calls.append({'purpose':purpose,'payload':payload})
        if self.fail:raise RuntimeError('offline')
        if schema is JudgeOutput:
            score=self.scores.pop(0) if len(self.scores)>1 else self.scores[0]
            return JudgeOutput(dimensions={k:score for k in JudgeOutput.model_fields['dimensions'].annotation.model_fields},
                issues=[] if score>=8 else ['Insufficient completeness'],rationale='TEST DOUBLE: deterministic fixture assessment.')
        e=payload['evidence'][0]
        return GeneratedDraft(content=e['text'],citations=[e['chunk_id']],limitations=['Test fixture only.'])

@pytest.fixture
def svc(tmp_path):
    p=Policy();emb=EmbeddingService();r=RetrievalService(VectorRepository(embedding=emb),p)
    r.ingest({'document_id':'lab','name':'inspection.csv','source_type':'observation','domain':'Quality',
        'text':'Laboratory original records were deleted. Investigation evidence is incomplete.',
        'metadata':{'dataset':'test','source_row':'2'}})
    r.ingest({'document_id':'training','name':'training.csv','source_type':'observation','domain':'Quality',
        'text':'Personnel training attendance records were incomplete.','metadata':{'dataset':'other'}})
    service=WorkflowService(WorkflowRepository(),r,FakeLLM(),p)
    from backend.database.postgres import connection
    from backend.api.identity import Principal
    from datetime import datetime,timezone,timedelta
    uid,sid=str(uuid.uuid4()),str(uuid.uuid4())
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',(uid,'SME','reviewer',uid))
        current.execute('INSERT INTO sessions(id,user_id,token_digest,expires_at) VALUES (%s,%s,%s,%s)',(sid,uid,sid,datetime.now(timezone.utc)+timedelta(hours=1)))
    service.test_principal=Principal(user_id=uid,session_id=sid,name='SME',role='reviewer')
    return service

def run(svc,question='Summarise laboratory original records deleted investigation evidence incomplete',review=False):
    w=svc.create(WorkflowRequest(question=question,require_review=review),svc.test_principal);return svc.run(w.workflow_id)

@pytest.mark.parametrize('query,agent,risk',[
 ('What is OAI?','EvidenceAgent','LOW'),
 ('How many inspections in 2025?','DataAnalyticsAgent','MEDIUM'),
 ('Explain laboratory observation','InspectionAssessmentAgent','MEDIUM'),
 ('Recommend a compliance response','InspectionAssessmentAgent','HIGH'),
 ('Explain contamination in an observation','InspectionAssessmentAgent','CRITICAL'),
 ('Recommend patient treatment','UnsupportedDomainAgent','HIGH')])
def test_routing(query,agent,risk):
    a,d=route(WorkflowRequest(question=query),Policy());assert d.selected_agent==agent;assert a.risk_level==risk
    assert d.routing_reason and d.matched_rules and d.confidence is None

def test_multiagent_is_bounded():
    a,d=route(WorkflowRequest(question='Compare inspection quality findings'),Policy())
    assert d.selected_agent=='DataAnalyticsAgent';assert d.secondary_agents==['InspectionAssessmentAgent']

def test_embedding_normalized_deterministic():
    e=EmbeddingService();a=e.embed_query('laboratory original records');assert a==e.embed_documents(['laboratory original records'])[0]
    assert len(a)==e.dimensions==768;assert math.isclose(sum(v*v for v in a),1,abs_tol=1e-5)
    assert e.version and all(math.isfinite(v) for v in a)

def test_chunk_metadata_boundaries():
    p=Policy(chunk_tokens=30,chunk_overlap=5)
    d={'document_id':'doc','name':'file.pdf','source_type':'pdf','page_number':7,'section':'Evidence','text':' '.join('term'+str(i) for i in range(70)),'metadata':{'country':'IN'}}
    chunks=chunk_document(d,p,EmbeddingService());assert len(chunks)==3
    assert all(c.page_number==7 and c.metadata=={'country':'IN'} and c.token_count<=30 for c in chunks)
    assert chunks[0].chunk_text.split()[-5:]==chunks[1].chunk_text.split()[:5]
    assert chunks[0].chunk_id==chunk_document(d,p,EmbeddingService())[0].chunk_id

def test_vector_persistence_filtering(svc):
    r=svc.retrieval;v=r.embedding.embed_query('Laboratory original records deleted')
    results=r.repository.search(v,{'dataset':'test'},5)
    assert results[0].chunk.document_id=='lab';assert results[0].similarity_score>0
    repo=VectorRepository(embedding=EmbeddingService());assert repo.search(v,{'dataset':'test'},5)==results
    assert not repo.search(v,{'dataset':'missing'},5)
    with pytest.raises(ValueError):repo.search(v,{'unsafe;drop':'x'},5)
    with pytest.raises(ValueError):repo.search([1.],{},5)

def test_ingestion_idempotent(svc):
    before=svc.retrieval.repository.count()
    svc.retrieval.ingest({'document_id':'lab','name':'inspection.csv','source_type':'observation','text':'Replaced content'})
    assert svc.retrieval.repository.count()==before
    assert 'Replaced' in svc.retrieval.repository.search(svc.retrieval.embedding.embed('Replaced content'),{'document_id':'lab'},5)[0].chunk.chunk_text

def test_trace_and_hit_miss(svc):
    t=svc.retrieval.search('Laboratory original records were deleted. Investigation evidence is incomplete.','q')
    assert t.retrieval_status=='STRONG_HIT';assert t.results[0].chunk.document_id=='lab'
    assert t.final_chunk_ids and all(c in [r.chunk.chunk_id for r in t.results] for c in t.final_chunk_ids)
    assert svc.retrieval.search('anything','q',{'dataset':'missing'}).retrieval_status=='MISS'

def test_weak_hit():
    # Fixed exact score brackets prove policy boundary behavior, without probabilistic claims.
    from backend.workflows.schemas import RetrievedChunk,Chunk
    class Repo:
        embedding=EmbeddingService()
        last_trace={}
        def search(self,*a,**kw):return [RetrievedChunk(chunk=Chunk(chunk_id='x',document_id='x',document_name='x',source_type='test',domain='Quality',chunk_index=0,chunk_text='x',token_count=1,embedding_model='x',embedding_version='x'),similarity_score=.6,rank=1)]
    assert RetrievalService(Repo(),Policy()).search('q','id').retrieval_status=='WEAK_HIT'

def test_high_risk_gate_cannot_be_bypassed(svc):
    s=run(svc,'Recommend a compliance response for laboratory original records deleted investigation evidence incomplete')
    assert s.status=='AWAITING_HUMAN_REVIEW';assert s.final_response is None
    assert svc.run(s.workflow_id).status==s.status
    with pytest.raises(Conflict):svc.finalize(s)
    assert svc.repository.get(s.workflow_id).status=='AWAITING_HUMAN_REVIEW'

def review(svc,state,decision,comment='Evidence checked.'):
    body=ReviewDecision(artifact_version=state.artifacts[-1].version,workflow_revision=state.revision,
        idempotency_key=str(uuid.uuid4()),reviewer='SME',comment=comment)
    updated=svc.review(state.workflow_id,decision,body,svc.test_principal)
    return svc.run(state.workflow_id,{'review_id':updated.reviews[-1]['review_id']})


def test_approval_releases_exact_artifact_and_persists(svc):
    state=run(svc,review=True);content=state.artifacts[-1].content;calls=len(svc.llm.calls)
    done=review(svc,state,'APPROVE')
    assert done.status=='COMPLETED' and done.final_response==content
    assert len(svc.llm.calls)==calls
    assert svc.repository.events(done.workflow_id)[-1]['event']=='finalized'


def test_rejection_returns_to_agent_and_judge(svc):
    state=run(svc,review=True)
    state=review(svc,state,'REJECT','Explain missing investigation evidence.')
    assert state.status=='AWAITING_HUMAN_REVIEW' and len(state.artifacts)==2
    assert state.artifacts[-1].previous_version==1
    assert any(x['payload'].get('reviewer_comment')=='Explain missing investigation evidence.' for x in svc.llm.calls)


def test_judge_failure_never_fabricates_score(svc):
    from backend.workflows.worker import run_once
    svc.llm.fail = True
    state = svc.create(WorkflowRequest(
        question='Summarise laboratory original records deleted investigation evidence incomplete',
        require_review=True), svc.test_principal)
    assert run_once(svc)
    s = svc.repository.get(state.workflow_id)
    assert s.status=='FAILED' and not s.artifacts and s.final_response is None

def test_low_judge_revises_and_stops(svc):
    svc.llm=FakeLLM([3]);s=run(svc,review=True)
    assert s.status=='FAILED' and s.iteration==3 and len(s.artifacts)==3
    assert all(a.evaluation.decision=='FAIL' for a in s.artifacts)
    assert s.final_response is None

@pytest.mark.parametrize('score,decision',[(9,'PASS'),(7,'REVISION_REQUIRED'),(3,'FAIL')])
def test_judge_thresholds(score,decision):
    result=EvaluationService(FakeLLM([score]),Policy()).evaluate('q','draft',[],[],{})
    assert result.overall_score==score*10 and result.decision==decision and result.same_model

def test_schema_and_policy_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):Policy(mandatory_hitl_risk_levels=[])
    with pytest.raises(ValidationError):Policy(chunk_tokens=30,chunk_overlap=30)
    with pytest.raises(ValidationError):ReviewDecision(artifact_version=1,reviewer=' ',comment='text')
    with pytest.raises(ValidationError):JudgeOutput(dimensions={},rationale='bad')

def test_optimistic_concurrency(svc):
    s=svc.create(WorkflowRequest(question='Explain inspection'),svc.test_principal);other=svc.repository.get(s.workflow_id)
    svc.repository.save(s,'first')
    with pytest.raises(Conflict):svc.repository.save(other,'stale')

def test_miss_does_not_call_model(svc):
    state=svc.create(WorkflowRequest(question='Explain records',filters={'dataset':'absent'}),svc.test_principal);s=svc.run(state.workflow_id)
    assert s.status=='COMPLETED' and 'No sufficiently' in s.final_response and not svc.llm.calls

def test_api_full_gate(tmp_path,monkeypatch,svc):
    from backend.api.main import create_app
    from backend.database.store import Store
    from pg_client import TestClient
    monkeypatch.setenv('WORKFLOW_DATA_DIR',str(tmp_path/'api'))
    monkeypatch.delenv('REGINSIGHT_ACCESS_KEY',raising=False)
    with TestClient(create_app(Store())) as c:
        c.app.state.workflows=svc
        response=c.post('/api/workflows',json={'question':'Summarise laboratory original records deleted investigation evidence incomplete','require_review':True})
        assert response.status_code==202;wid=response.json()['workflow_id']
        state=svc.run(wid)
        assert c.get('/api/workflows/'+wid).json()['status']=='AWAITING_HUMAN_REVIEW'
        assert c.post('/api/workflows/'+wid+'/resume').status_code==409
        assert c.get('/api/workflows/'+wid+'/retrieval').json()['final_chunk_ids']
        assert c.get('/api/workflows/'+wid+'/evaluation').json()[0]['decision']=='PASS'
        assert c.get('/api/workflows/reviews/pending').json()
        body={'artifact_version':1,'workflow_revision':state.revision,'idempotency_key':str(uuid.uuid4()),'reviewer':'SME','comment':'Verified source.'}
        response=c.post('/api/workflows/'+wid+'/reviews/approve',json=body)
        assert response.status_code==200
        state=svc.run(wid,{'review_id':response.json()['reviews'][-1]['review_id']})
        assert state.status=='COMPLETED'
        assert c.post('/api/workflows/'+wid+'/reviews/approve',json=body).status_code==200
        assert c.get('/api/workflows/'+wid+'/trace').json()['reviews'][0]['decision']=='APPROVE'
        assert c.get('/api/workflows/missing').status_code==404
