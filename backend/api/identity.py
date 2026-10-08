"""Persisted individual access keys and revocable sessions."""
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, Request
from pydantic import BaseModel
from backend.database.postgres import connection


class Principal(BaseModel):
    user_id: str
    session_id: str
    name: str
    role: str


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def create_session(access_key):
    with connection() as current:
        user=current.execute('SELECT id FROM users WHERE key_digest=%s AND active', (digest(access_key),)).fetchone()
        if not user:
            raise HTTPException(401, 'Invalid access key')
        token=secrets.token_urlsafe(48)
        current.execute('INSERT INTO sessions(id,user_id,token_digest,expires_at) VALUES (%s,%s,%s,%s)',
            (str(uuid.uuid4()),user['id'],digest(token),datetime.now(timezone.utc)+timedelta(hours=8)))
    return token


def authenticate(token):
    if not token:
        return None
    with connection() as current:
        row=current.execute('''SELECT u.id user_id,s.id session_id,u.name,u.role FROM sessions s
            JOIN users u ON u.id=s.user_id WHERE s.token_digest=%s AND s.expires_at>now() AND u.active''', (digest(token),)).fetchone()
    return Principal(**row) if row else None


def principal(request: Request):
    value=getattr(request.state,'principal',None)
    if value is None:
        raise HTTPException(401,'Sign in to access this resource')
    return value


def reviewer(request: Request):
    value=principal(request)
    if value.role not in ('reviewer','admin'):
        raise HTTPException(403,'Reviewer permission required')
    return value


def revoke_session(token):
    with connection() as current:
        current.execute('UPDATE sessions SET expires_at=now() WHERE token_digest=%s', (digest(token or ''),))
