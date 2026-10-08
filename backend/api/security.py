"""Individual PostgreSQL sessions plus existing CSRF, body, host and header controls."""
import json
import logging
import os
import secrets
import time
from collections import OrderedDict, deque
from urllib.parse import urlsplit
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ConfigDict
from starlette.middleware.trustedhost import TrustedHostMiddleware

class Login(BaseModel):
    model_config=ConfigDict(extra='forbid')
    access_key:str=Field(min_length=1,max_length=512)

def install_security(app):
    from backend.api.identity import authenticate, create_session, revoke_session
    production=os.getenv('REGINSIGHT_ENV','local')=='production'
    hosts=[h.strip() for h in os.getenv('REGINSIGHT_ALLOWED_HOSTS','localhost,127.0.0.1,::1,testserver').split(',')]
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=hosts)
    buckets=OrderedDict()
    def authenticated(request):
        return getattr(request.state,'principal',None) is not None
    @app.middleware('http')
    async def protect(request,call_next):
        started=time.perf_counter()
        path=request.url.path
        if request.method not in ('GET','HEAD','OPTIONS'):
            origin=request.headers.get('origin')
            if origin and (urlsplit(origin).netloc!=request.headers.get('host') or urlsplit(origin).scheme!=request.url.scheme):
                return JSONResponse({'detail':'Cross-origin write request rejected.'},status_code=403)
            if request.headers.get('sec-fetch-site')=='cross-site':return JSONResponse({'detail':'Cross-site request rejected.'},status_code=403)
        if path.startswith('/api/'):
            public=path in ('/api/auth/status','/api/auth/login','/api/auth/logout','/api/health')
            from starlette.concurrency import run_in_threadpool
            try:
                request.state.principal=await run_in_threadpool(authenticate,request.cookies.get('reginsight_session',''))
            except Exception:
                return JSONResponse({'detail':'Authentication database unavailable.'},status_code=503)
            request.state.request_id=secrets.token_hex(16)
            if not public and not authenticated(request):return JSONResponse({'detail':'Sign in to access the workspace.'},status_code=401)
            now=time.monotonic();identity=(request.client.host if request.client else 'unknown', 'login' if path=='/api/auth/login' else 'api')
            bucket=buckets.setdefault(identity,deque());buckets.move_to_end(identity)
            while bucket and bucket[0]<now-60:bucket.popleft()
            if len(bucket)>=(10 if identity[1]=='login' else 180):return JSONResponse({'detail':'Too many requests. Try again in one minute.'},status_code=429,headers={'Retry-After':'60'})
            bucket.append(now)
            while len(buckets)>4096:buckets.popitem(last=False)
            if request.method not in ('GET','HEAD','OPTIONS'):
                # Enforce streamed bodies too; Content-Length alone is not a boundary.
                size=0;parts=[]
                async for part in request.stream():
                    size+=len(part)
                    if size>4*1024*1024:return JSONResponse({'detail':'Request exceeds 4 MB.'},status_code=413)
                    parts.append(part)
                request._body=b''.join(parts)
        response=await call_next(request)
        if path.startswith('/api/'):
            actor=getattr(request.state,'principal',None)
            route=request.scope.get('route')
            logging.getLogger('reginsight.requests').info(json.dumps({
                'event':'http_request','request_id':request.state.request_id,
                'user_id':actor.user_id if actor else None,'method':request.method,
                'route':getattr(route,'path','unmatched'),'status':response.status_code,
                'duration_ms':round((time.perf_counter()-started)*1000,2)}))
            response.headers['X-Request-ID']=request.state.request_id
        response.headers.update({'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin',
          'Permissions-Policy':'camera=(), microphone=(), geolocation=()',
          'Content-Security-Policy':"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"})
        if path.startswith('/api/'):response.headers['Cache-Control']='no-store'
        if production:response.headers['Strict-Transport-Security']='max-age=31536000'
        return response
    @app.get('/api/auth/status')
    def status(request:Request):return {'required':True,'authenticated':authenticated(request),'mode':'individual-key','user':request.state.principal.model_dump() if authenticated(request) else None}
    @app.post('/api/auth/login')
    def login(body:Login):
        session_token=create_session(body.access_key)
        response=JSONResponse({'authenticated':True})
        response.set_cookie('reginsight_session',session_token,httponly=True,secure=production,samesite='strict',max_age=28800,path='/')
        return response
    @app.post('/api/auth/logout')
    def logout(request:Request):
        revoke_session(request.cookies.get('reginsight_session',''))
        response=JSONResponse({'authenticated':False});response.delete_cookie('reginsight_session',path='/');return response
