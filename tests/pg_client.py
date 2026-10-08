"""Authenticated client for domain tests; security tests use the raw client."""
import secrets
import uuid
from fastapi.testclient import TestClient as BaseClient
from backend.database.postgres import connection
from backend.api.identity import digest


class TestClient(BaseClient):
    __test__=False
    def __enter__(self):
        result=super().__enter__()
        key=secrets.token_urlsafe(32)
        with connection() as current:
            current.execute('INSERT INTO users(id,name,role,key_digest) VALUES (%s,%s,%s,%s)',(str(uuid.uuid4()),'Regression reviewer','reviewer',digest(key)))
        response=self.post('/api/auth/login',json={'access_key':key})
        assert response.status_code==200,response.text
        return result
