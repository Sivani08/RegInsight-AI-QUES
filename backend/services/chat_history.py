"""PostgreSQL conversation ownership, ordered turns, and bounded audit snapshots."""
import os
import re
import uuid

from fastapi import HTTPException
from psycopg.types.json import Jsonb

from backend.database.postgres import connection
from backend.semantic.models import Context, QueryRequest, Turn


def sanitize(value):
    """Remove recognizable credentials; never collect HTTP authentication context."""
    if isinstance(value, dict):
        return {key: '[REDACTED]' if re.search(
            r'password|access_key|api_key|authorization|cookie|token_digest|key_digest', key, re.I
        ) else sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    if not isinstance(value, str):
        return value
    for name in ('DATABASE_URL', 'POSTGRES_PASSWORD', 'OPENAI_API_KEY', 'AI_API_KEY',
                 'ANTHROPIC_API_KEY', 'REGINSIGHT_DB_VIEWER_PASSWORD'):
        secret = os.getenv(name)
        if secret:
            value = value.replace(secret, '[REDACTED]')
    value = re.sub(r'(?i)(?:postgres(?:ql)?(?:\+psycopg)?://)[^\s]+', '[REDACTED DATABASE URL]', value)
    value = re.sub(r'\bsk-[A-Za-z0-9_-]{16,}', '[REDACTED]', value)
    return re.sub(
        r'(?i)\b(password|access[_ -]?key|api[_ -]?key|authorization|bearer|reginsight_session)'
        r'([\s\"\x27:=]+)(?:Bearer\s+)?[^\s\"\x27,}]+',
        r'\1\2[REDACTED]', value)


def owned_session(current, session_id, user_id, lock=False):
    row = current.execute(
        'SELECT * FROM chat_sessions WHERE id=%s AND user_id=%s' + (' FOR UPDATE' if lock else ''),
        (session_id, user_id)).fetchone()
    if row is None:
        raise HTTPException(404, 'Conversation not found')
    return row


def start_turn(body, user_id, request_id):
    """Reserve a consecutive user/assistant pair before accepting the stream."""
    session_id = str(body.session_id or uuid.uuid4())
    question = sanitize(body.question)
    filters = sanitize(body.filters.model_dump(mode='json', exclude_none=True))
    with connection() as current:
        if body.session_id is None:
            current.execute('INSERT INTO chat_sessions(id,user_id,title,filters) VALUES (%s,%s,%s,%s)',
                            (session_id, user_id, question[:120], Jsonb(filters)))
        session = owned_session(current, session_id, user_id, lock=True)
        if session['filters'] != filters:
            raise HTTPException(409, 'Start a new conversation after changing filters')
        if current.execute("SELECT 1 FROM chat_messages WHERE session_id=%s AND status='RUNNING'",
                           (session_id,)).fetchone():
            raise HTTPException(409, 'A response is already running in this conversation')
        rows = current.execute('SELECT role,content,sequence_number FROM chat_messages '
                               'WHERE session_id=%s ORDER BY sequence_number DESC LIMIT 12',
                               (session_id,)).fetchall()
        sequence = rows[0]['sequence_number'] + 1 if rows else 1
        user_message_id, assistant_message_id = str(uuid.uuid4()), str(uuid.uuid4())
        current.execute('''INSERT INTO chat_messages
            (id,session_id,user_id,sequence_number,role,content,request_id,status,completed_at)
            VALUES (%s,%s,%s,%s,'user',%s,%s,'COMPLETED',now())''',
            (user_message_id, session_id, user_id, sequence, question, request_id))
        current.execute('''INSERT INTO chat_messages
            (id,session_id,user_id,sequence_number,role,request_id,reply_to_id,status,agent_name)
            VALUES (%s,%s,%s,%s,'assistant',%s,%s,'RUNNING','RegInsightChatAgent')''',
            (assistant_message_id, session_id, user_id, sequence + 1, request_id, user_message_id))
        current.execute('UPDATE chat_sessions SET last_activity_at=now(),updated_at=now() WHERE id=%s',
                        (session_id,))
        previous = current.execute('''SELECT t.output_summary FROM chat_tool_executions t
            JOIN chat_messages m ON m.id=t.message_id WHERE m.session_id=%s
            ORDER BY m.sequence_number DESC LIMIT 1''', (session_id,)).fetchone()
    context = previous['output_summary'].get('context', {}) if previous else {}
    query = QueryRequest(**{**body.model_dump(exclude={'session_id', 'history', 'context'}),
                            'question': question,
                            'history': [Turn(role=row['role'], content=row['content'][:4000])
                                        for row in reversed(rows)],
                            'context': Context(**context)})
    return {'session_id': session_id, 'user_message_id': user_message_id,
            'assistant_message_id': assistant_message_id, 'request_id': request_id}, query


def save_retrieval(message_id, request_id, body, event):
    event = sanitize(event)
    sources = event.get('sources', [])
    analytics = event.get('analytics')
    trace = event.get('trace', {})
    mode = trace.get('mode', 'deterministic' if analytics else 'keyword')
    route = 'dashboard_analytics' if analytics else 'reference_retrieval' if sources else 'general'
    with connection() as current:
        current.execute('UPDATE chat_messages SET route=%s,service_name=%s,retrieval_mode=%s WHERE id=%s',
                        (route, 'DashboardInsights' if analytics else 'RegInsightChatAgent.retrieve', mode, message_id))
        current.execute('''INSERT INTO chat_retrieval_events
            (message_id,request_id,retrieval_mode,query_text,filters,candidate_count,
             selected_count,candidates,latency_ms) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
            (message_id, request_id, mode, trace.get('query', body.question),
             Jsonb(sanitize(body.filters.model_dump(mode='json', exclude_none=True))),
             trace.get('candidate_count'), len(sources), Jsonb(trace.get('candidates', [])),
             event.get('retrieval_ms')))
        for rank, source in enumerate(sources, 1):
            current.execute('''INSERT INTO chat_message_evidence
                (message_id,source_id,chunk_id,document_id,observation_id,source_name,source_type,
                 locator,evidence_text,source_metadata,vector_score,keyword_score,hybrid_score,final_score,rank)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (message_id, source['id'], source.get('chunk_id'), source.get('document_id'),
                 source.get('observation_id'), source['title'], source['kind'], source.get('locator'),
                 source['text'], Jsonb(source), source.get('vector_score'), source.get('keyword_score'),
                 source.get('hybrid_score'), source.get('final_score'), rank))
        if analytics:
            timing = trace.get('tool_timing', {})
            current.execute('''INSERT INTO chat_tool_executions
                (message_id,request_id,tool_name,service_name,input_summary,output_summary,
                 evidence_snapshot_id,status,started_at,completed_at,latency_ms)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'COMPLETED',%s,coalesce(%s,now()),%s)''',
                (message_id, request_id, 'query', 'DashboardInsights', Jsonb(analytics['semantic_plan']),
                 Jsonb(analytics), analytics['evidence_id'], timing.get('started_at'),
                 timing.get('completed_at'), timing.get('latency_ms')))


def finish_turn(message_id, event, latency_ms):
    event = sanitize(event)
    failed = event.get('type') == 'error' or event.get('mode') in ('evidence_only', 'model_unavailable')
    content = event.get('answer', event.get('message', 'Response interrupted. Please retry.'))
    input_tokens, output_tokens = event.get('input_tokens'), event.get('output_tokens')
    total_tokens = input_tokens + output_tokens if input_tokens is not None and output_tokens is not None else None
    with connection() as current:
        row = current.execute('''UPDATE chat_messages SET content=%s,status=%s,model_name=%s,
            response_mode=%s,error_message=%s,input_token_count=%s,output_token_count=%s,
            total_token_count=%s,latency_ms=%s,guardrail_checks=%s,completed_at=now()
            WHERE id=%s AND status='RUNNING' RETURNING session_id''',
            (content, 'FAILED' if failed else 'COMPLETED', event.get('model'), event.get('mode'),
             content if failed else None, input_tokens, output_tokens, total_tokens, latency_ms,
             Jsonb(event.get('checks', [])), message_id)).fetchone()
        if not row:
            return
        if not failed:
            for order, citation in enumerate(dict.fromkeys(event.get('citations', [])), 1):
                current.execute('INSERT INTO chat_message_citations(message_id,citation_id,display_order) '
                                'VALUES (%s,%s,%s)', (message_id, citation, order))
        current.execute('UPDATE chat_sessions SET last_activity_at=now(),updated_at=now() WHERE id=%s',
                        (row['session_id'],))


def expire_interrupted_turns():
    """Recover abandoned executions; local generation is capped at 45 seconds."""
    with connection() as current:
        current.execute("""UPDATE chat_messages SET status='FAILED',completed_at=now(),
            content='Response interrupted. Please retry.',error_message='Response interrupted. Please retry.'
            WHERE status='RUNNING' AND started_at < now()-interval '5 minutes'""")


def list_sessions(user_id):
    with connection() as current:
        return current.execute('SELECT id,title,filters,last_activity_at FROM chat_sessions '
                               'WHERE user_id=%s ORDER BY last_activity_at DESC LIMIT 100', (user_id,)).fetchall()


def read_session(session_id, user_id):
    with connection() as current:
        session = owned_session(current, session_id, user_id)
        rows = current.execute('SELECT * FROM chat_messages WHERE session_id=%s ORDER BY sequence_number',
                               (session_id,)).fetchall()
        for row in rows:
            row['sources'] = [item['source_metadata'] for item in current.execute(
                'SELECT source_metadata FROM chat_message_evidence WHERE message_id=%s ORDER BY rank',
                (row['id'],))]
            row['citations'] = [item['citation_id'] for item in current.execute(
                'SELECT citation_id FROM chat_message_citations WHERE message_id=%s ORDER BY display_order',
                (row['id'],))]
            calculation = current.execute('SELECT output_summary FROM chat_tool_executions WHERE message_id=%s',
                                          (row['id'],)).fetchone()
            row['analytics'] = calculation['output_summary'] if calculation else None
    return {'session': session, 'messages': rows}
