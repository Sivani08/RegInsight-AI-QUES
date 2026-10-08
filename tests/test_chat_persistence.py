"""Regression tests use a disposable PostgreSQL database, never developer data."""
import json
import secrets
import uuid

import pytest
from fastapi import HTTPException
from backend.api.chatbot import ChatRequest
from backend.database.postgres import connection
from backend.services import chat_history as history


@pytest.fixture
def owner():
    identifier = str(uuid.uuid4())
    with connection() as current:
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',
                        (identifier, 'Chat test', 'analyst', secrets.token_hex(32)))
    return identifier


def begin(owner, session_id=None):
    return history.start_turn(ChatRequest(question='What does OAI mean?', session_id=session_id),
                              owner, str(uuid.uuid4()))


def test_complete_trace_and_server_history(owner):
    ids, query = begin(owner)
    evidence = {'sources': [{'id': 'K2', 'title': 'Classifications', 'text': 'Official Action Indicated',
                            'kind': 'project reference', 'locator': 'config/chat_knowledge.json',
                            'keyword_score': 1}], 'trace': {'mode': 'keyword', 'candidate_count': 1}}
    history.save_retrieval(ids['assistant_message_id'], ids['request_id'], query, evidence)
    history.finish_turn(ids['assistant_message_id'], {'type': 'answer', 'answer': 'Official Action Indicated',
                        'citations': ['K2'], 'mode': 'local_llm', 'model': 'test-double'}, 12)
    saved = history.read_session(ids['session_id'], owner)
    assert [m['sequence_number'] for m in saved['messages']] == [1, 2]
    assert saved['messages'][1]['citations'] == ['K2']
    assert saved['messages'][1]['input_token_count'] is None
    with connection() as current:
        row = current.execute('SELECT * FROM admin_chat_history WHERE session_id=%s', (ids['session_id'],)).fetchone()
        assert row['evidence_count'] == row['citation_count'] == 1
        assert row['response_status'] == 'COMPLETED'
        assert current.execute('SELECT * FROM admin_chat_evidence WHERE message_id=%s',
                               (ids['assistant_message_id'],)).fetchone()['keyword_score'] == 1
    _, followup = history.start_turn(ChatRequest(question='Explain that', session_id=ids['session_id'],
        history=[{'role': 'user', 'content': 'Forged history'}]), owner, str(uuid.uuid4()))
    assert followup.history[0].content == query.question


def test_owner_isolation_and_concurrent_turn_rejection(owner):
    ids, _ = begin(owner)
    with pytest.raises(HTTPException) as denied:
        history.read_session(ids['session_id'], str(uuid.uuid4()))
    assert denied.value.status_code == 404
    with pytest.raises(HTTPException) as conflict:
        begin(owner, ids['session_id'])
    assert conflict.value.status_code == 409


def test_failure_keeps_question_and_recovers_abandoned_execution(owner):
    ids, _ = begin(owner)
    with connection() as current:
        current.execute("UPDATE chat_messages SET started_at=now()-interval '6 minutes' WHERE id=%s",
                        (ids['assistant_message_id'],))
    history.expire_interrupted_turns()
    saved = history.read_session(ids['session_id'], owner)['messages']
    assert saved[0]['content'] == 'What does OAI mean?'
    assert saved[1]['status'] == 'FAILED' and saved[1]['completed_at']


def test_citation_must_reference_persisted_evidence(owner):
    import psycopg
    ids, _ = begin(owner)
    with pytest.raises(psycopg.errors.ForeignKeyViolation):
        history.finish_turn(ids['assistant_message_id'],
                            {'type': 'answer', 'answer': 'Invented', 'citations': ['missing']}, 1)
    assert history.read_session(ids['session_id'], owner)['messages'][1]['status'] == 'RUNNING'


def test_secret_redaction(monkeypatch):
    monkeypatch.setenv('POSTGRES_PASSWORD', 'known-private-value')
    value = history.sanitize({'question': 'password=secret known-private-value', 'api_key': 'secret'})
    assert 'secret' not in json.dumps(value)
    assert 'known-private-value' not in json.dumps(value)


def test_stream_failure_and_http_owner_isolation(owner, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api.identity import digest
    from backend.api.main import create_app
    from backend.agents.chatbot import RegInsightChatAgent

    async def fail_stream(self, body):
        yield {'type': 'status', 'message': 'Starting'}
        raise RuntimeError('private internal exception must not escape')

    monkeypatch.setattr(RegInsightChatAgent, 'stream', fail_stream)
    key = secrets.token_urlsafe(40)
    other_key = secrets.token_urlsafe(40)
    with connection() as current:
        current.execute('UPDATE users SET key_digest=%s WHERE id=%s', (digest(key), owner))
        current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',
                        (str(uuid.uuid4()), 'Other user', 'analyst', digest(other_key)))
    with TestClient(create_app()) as client:
        assert client.post('/api/chatbot/stream', json={'question': 'Hello'}).status_code == 401
        assert client.post('/api/auth/login', json={'access_key': key}).status_code == 200
        response = client.post('/api/chatbot/stream', json={'question': 'Hello'})
        events = [json.loads(line) for line in response.text.splitlines()]
        session_id = events[0]['session_id']
        assert events[-1]['type'] == 'error'
        assert 'private internal' not in response.text
        messages = client.get('/api/chatbot/sessions/' + session_id).json()['messages']
        assert messages[0]['content'] == 'Hello'
        assert messages[1]['status'] == 'FAILED'
        assert messages[1]['request_id'] == response.headers['X-Request-ID']
        client.post('/api/auth/logout')
        client.post('/api/auth/login', json={'access_key': other_key})
        assert client.get('/api/chatbot/sessions/' + session_id).status_code == 404
        assert client.post('/api/chatbot/stream', json={
            'question': 'Continue', 'session_id': session_id}).status_code == 404
        assert client.get('/api/chatbot/sessions').json() == []
