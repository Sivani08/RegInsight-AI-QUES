"""Real PostgreSQL/checkpointer tests with deterministic model responses."""
import os
import secrets
import uuid
import pytest
from fastapi.testclient import TestClient
from backend.database.postgres import connection
from backend.api.identity import digest
from backend.api.main import create_app
from backend.workflows.schemas import GeneratedDraft, JudgeOutput, JudgeScores

pytestmark=pytest.mark.skipif(not os.getenv('DATABASE_URL','').startswith('postgresql'),reason='Requires migrated PostgreSQL with pgvector and installed local embeddings')


class TestModel:
    last_call={'purpose':'test-double','model':'deterministic-test-double'}
    calls=0
    def generate(self,model,system,payload,schema,purpose):
        self.calls+=1
        if schema is GeneratedDraft:
            return GeneratedDraft(content='The evidence describes inspection outcomes.',citations=[payload['evidence'][0]['chunk_id']],limitations=['Decision support only.'])
        return JudgeOutput(dimensions=JudgeScores(**{name:9 for name in JudgeScores.model_fields}),issues=[],rationale='Deterministic test fixture; not a live model evaluation.')


def user(role):
    identifier=str(uuid.uuid4())
    key=secrets.token_urlsafe(32)
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)', (identifier,'Test '+role,role,digest(key)))
    return key


@pytest.fixture
def client():
    with TestClient(create_app()) as client:
        client.app.state.workflows.llm=TestModel()
        yield client


def login(client,role='reviewer'):
    response=client.post('/api/auth/login',json={'access_key':user(role)})
    assert response.status_code==200,response.text


def start(client):
    response=client.post('/api/workflows',json={'question':'Explain regulatory significance of OAI VAI NAI inspection outcome classifications.','require_review':True})
    assert response.status_code==202,response.text
    identifier=response.json()['workflow_id']
    state=client.app.state.workflows.run(identifier)
    assert state.status=='AWAITING_HUMAN_REVIEW'
    return state


def body(state,modified=None):
    return {'artifact_version':state.artifacts[-1].version,'workflow_revision':state.revision,
        'idempotency_key':str(uuid.uuid4()),'reviewer':'Forged client name','comment':'Verified test evidence.',
        **({'modified_output':modified} if modified else {})}


def test_approve_checkpoint_resume_and_idempotency(client):
    login(client)
    state=start(client)
    payload=body(state)
    path='/api/workflows/'+state.workflow_id+'/reviews/approve'
    first=client.post(path,json=payload)
    assert first.status_code==200,first.text
    duplicate=client.post(path,json=payload)
    assert duplicate.status_code==200,duplicate.text
    assert len(duplicate.json()['reviews'])==1
    assert first.json()['reviews'][0]['reviewer']!='Forged client name'
    calls=client.app.state.workflows.llm.calls
    # A fresh service/checkpointer connection reloads the interrupt from PostgreSQL.
    from backend.workflows.factory import create_workflows
    restarted=create_workflows(client.app.state.service)
    restarted.llm=client.app.state.workflows.llm
    state=restarted.run(state.workflow_id,{'review_id':first.json()['reviews'][-1]['review_id']})
    assert state.status=='COMPLETED'
    assert state.final_response==state.artifacts[-1].content
    assert restarted.llm.calls==calls
    again=restarted.run(state.workflow_id,{'review_id':first.json()['reviews'][-1]['review_id']})
    assert again.revision==state.revision


def test_modify_preserves_original(client):
    login(client)
    state=start(client)
    original=state.artifacts[-1].content
    modified='The available evidence supports a limited inspection summary.'
    response=client.post('/api/workflows/'+state.workflow_id+'/reviews/modify',json=body(state,modified))
    assert response.status_code==200,response.text
    review=response.json()['reviews'][-1]
    state=client.app.state.workflows.run(state.workflow_id,{'review_id':review['review_id']})
    assert state.final_response==modified
    assert state.artifacts[-1].content==original
    assert review['original_output']==original


def test_reject_bounded_correction(client):
    login(client)
    state=start(client)
    for _ in range(state.policy['maximum_agent_iterations']):
        response=client.post('/api/workflows/'+state.workflow_id+'/reviews/reject',json=body(state))
        assert response.status_code==200,response.text
        state=client.app.state.workflows.run(state.workflow_id,{'review_id':response.json()['reviews'][-1]['review_id']})
        if state.status=='FAILED':
            break
    assert state.status=='FAILED'
    assert state.final_response is None
    assert state.iteration==state.policy['maximum_agent_iterations']


def test_user_isolation_and_reviewer_permissions(client):
    login(client,'analyst')
    state=start(client)
    denied=client.post('/api/workflows/'+state.workflow_id+'/reviews/approve',json=body(state))
    assert denied.status_code==403
    client.post('/api/auth/logout')
    login(client,'analyst')
    assert client.get('/api/workflows/'+state.workflow_id).status_code==404
    assert client.get('/api/workflows/'+state.workflow_id+'/trace').status_code==404


def test_stale_review_and_invalid_modification(client):
    login(client)
    state=start(client)
    payload=body(state)
    payload['workflow_revision']-=1
    assert client.post('/api/workflows/'+state.workflow_id+'/reviews/approve',json=payload).status_code==409
    invalid=body(state,'This assessment proves 999999 cases.')
    assert client.post('/api/workflows/'+state.workflow_id+'/reviews/modify',json=invalid).status_code==400


def test_terminal_job_failure_updates_workflow(client):
    from backend.workflows import jobs
    login(client)
    response=client.post('/api/workflows',json={'question':'Explain inspection classifications.'})
    identifier=response.json()['workflow_id']
    # Claim only this test's job, without consuming jobs left by other integration cases.
    with connection() as current:
        job=current.execute("UPDATE background_jobs SET status='RUNNING',attempts=3,lease_token=%s WHERE workflow_id=%s RETURNING *",(str(uuid.uuid4()),identifier)).fetchone()
    assert jobs.finish(job,'Simulated terminal failure')
    state=client.app.state.workflows.repository.get(identifier)
    assert state.status=='FAILED' and state.final_response is None
    assert client.app.state.workflows.repository.events(identifier)[-1]['event']=='job_failed'


def test_review_race_commits_one_decision(client):
    from concurrent.futures import ThreadPoolExecutor
    from backend.api.identity import Principal
    from backend.workflows.schemas import ReviewDecision
    from backend.workflows.repository import Conflict
    login(client)
    state=start(client)
    service=client.app.state.workflows
    principal=Principal(**client.get('/api/auth/status').json()['user'])
    def decide(action):
        try:
            service.review(state.workflow_id,action,ReviewDecision(**body(state)),principal)
            return 'saved'
        except Conflict:
            return 'conflict'
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(decide,['APPROVE','REJECT']))
    assert sorted(results)==['conflict','saved']
    assert len(service.repository.get(state.workflow_id).reviews)==1
