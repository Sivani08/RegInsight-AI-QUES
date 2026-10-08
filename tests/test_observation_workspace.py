import pytest
from backend.services import observations as s
from backend.analytics.observation_rubric import tag_rules
from data_engineering.observation_demo import records

def test_complete_batch_pandas_denominators_and_export(tmp_path):
    db='observation_workspace';run=s.run_batch(path=db)
    assert run['completed']==72 and run['failed']==0
    summary=s.summaries(run['id'],db)
    assert sum(r['observations'] for r in summary['categories'])==72
    assert all(r['inspections']==3 and r['repeats']==2 for r in summary['recurrence'])
    assert summary['evaluation']['reviewed_count']==0
    s.export(run['id'],tmp_path/'export',db)
    assert (tmp_path/'export/recurrence.csv').exists()

def test_rubric_negation_and_unknown():
    assert tag_rules('No evidence of audit trail failures was observed.')['severity']=='Insufficient evidence'
    assert tag_rules('Unclear handwritten note.')['category']=='Unclassified'
    assert tag_rules('Audit trail records were deleted.')['severity']=='Critical'

def test_review_evidence_concurrency_and_evaluation(tmp_path):
    db='observation_workspace';run=s.run_batch(path=db,inputs=records()[:1]);row=s.rows(run['id'],db)[0]
    value={'category':'Records and data integrity','severity':'High','themes':['Data Integrity'],'evidence_quotes':[row['observation_text']]}
    s.review(run['id'],row['observation_id'],value,1,'Test reviewer','Test correction',db)
    assert s.summaries(run['id'],db)['evaluation']['severity_accuracy']==0
    assert s.rows(run['id'],db)[0]['prediction']['severity']=='Critical'
    with pytest.raises(ValueError,match='changed'):s.review(run['id'],row['observation_id'],value,1,'Test reviewer','stale',db)
    with pytest.raises(ValueError,match='quote'):s.validate({**value,'evidence_quotes':['invented evidence']},row['observation_text'])

def test_claude_missing_credentials_is_not_success(tmp_path,monkeypatch):
    monkeypatch.delenv('AI_API_KEY',raising=False);monkeypatch.delenv('ANTHROPIC_API_KEY',raising=False)
    with pytest.raises(ValueError,match='Configure'):s.run_batch('claude','claude-sonnet-test','observation_workspace')

def test_provider_failure_keeps_failed_rows(tmp_path,monkeypatch):
    monkeypatch.setenv('ANTHROPIC_API_KEY','test-not-real')
    def fail(*args):raise TimeoutError('secret')
    monkeypatch.setattr(s,'claude_tag',fail)
    run=s.run_batch('claude','claude-sonnet-test','observation_workspace',records()[:2])
    assert run['status']=='partial_failed' and run['failed']==2
    assert all(r['prediction'] is None and r['error']=='TimeoutError' for r in s.rows(run['id'],'observation_workspace'))

def test_duplicate_observations_rejected(tmp_path):
    record=records()[0]
    with pytest.raises(ValueError,match='unique'):s.run_batch(path='observation_workspace',inputs=[record,record])

def test_workspace_api_review_and_history(tmp_path,monkeypatch):
    from pg_client import TestClient
    from backend.api.main import create_app
    from backend.database.store import Store
    from backend.api import observation_workspace as routes
    db='observation_workspace';run=s.run_batch(path=db,inputs=records()[:1])
    originals={name:getattr(s,name) for name in ['get_run','rows','summaries','review','connect']}
    for name in ['get_run','rows','summaries','review']:
        def wrapper(*args,_name=name,**kwargs):
            import inspect
            bound=inspect.signature(originals[_name]).bind_partial(*args,**kwargs)
            bound.arguments['path']=db
            return originals[_name](*bound.args,**bound.kwargs)
        monkeypatch.setattr(routes.s,name,wrapper)
    monkeypatch.setattr(routes.s,'connect',lambda path=db:originals['connect'](path))
    with TestClient(create_app(Store())) as c:
        result=c.get('/api/observation-workspace').json();assert result['total']==1
        row=result['rows'][0]
        body={'run_id':run['id'],'observation_id':row['observation_id'],'version':1,'reviewer':'Test reviewer','note':'API test','category':'Records and data integrity','severity':'Critical','themes':['Data Integrity'],'evidence_quotes':[row['observation_text']]}
        assert c.post('/api/observation-workspace/review',json=body).status_code==200
        assert c.post('/api/observation-workspace/review',json=body).status_code==409
        assert len(c.get('/api/observation-workspace/history',params={'run_id':run['id'],'observation_id':row['observation_id']}).json())==1
        assert c.get('/api/observation-workspace/export',params={'run_id':run['id']}).json()['summary']['reviewed']==1
