"""Authenticated streaming with commit-before-delivery audit persistence."""
import json
import time
from uuid import UUID
import anyio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool
from backend.api.identity import principal
from backend.semantic.models import QueryRequest
from backend.services import chat_history

router=APIRouter(prefix='/api/chatbot')


class ChatRequest(QueryRequest):
    session_id: UUID | None = None


@router.get('/sessions')
def sessions(request: Request):
    return chat_history.list_sessions(principal(request).user_id)


@router.get('/sessions/{session_id}')
def conversation(session_id: UUID, request: Request):
    return chat_history.read_session(str(session_id), principal(request).user_id)

@router.get('/status')
async def status(request:Request):
    return await request.app.state.chatbot.status()

@router.post('/stream')
async def chat(request: Request, body: ChatRequest):
    identifiers, query = await run_in_threadpool(
        chat_history.start_turn, body, principal(request).user_id, request.state.request_id)
    message_id = identifiers['assistant_message_id']

    async def events():
        started = time.perf_counter()
        completed = False
        try:
            yield json.dumps({'type': 'session', **identifiers}) + '\n'
            async for event in request.app.state.chatbot.stream(query):
                if event['type'] == 'evidence':
                    await run_in_threadpool(chat_history.save_retrieval, message_id,
                                            identifiers['request_id'], query, event)
                if event['type'] in ('answer', 'error'):
                    await run_in_threadpool(chat_history.finish_turn, message_id, event,
                                            round((time.perf_counter() - started) * 1000, 2))
                    completed = True
                yield json.dumps(chat_history.sanitize(event), ensure_ascii=False, default=str) + '\n'
        except Exception:
            error = {'type': 'error', 'message': 'Chat execution failed. Please retry.'}
            await run_in_threadpool(chat_history.finish_turn, message_id, error,
                                    round((time.perf_counter() - started) * 1000, 2))
            completed = True
            yield json.dumps(error) + '\n'
        finally:
            if not completed:
                with anyio.CancelScope(shield=True):
                    await run_in_threadpool(chat_history.finish_turn, message_id,
                        {'type': 'error', 'message': 'Response interrupted. Please retry.'},
                        round((time.perf_counter() - started) * 1000, 2))
    return StreamingResponse(events(),media_type='application/x-ndjson',headers={'Cache-Control':'no-store','X-Accel-Buffering':'no'})
