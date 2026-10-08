from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Query, Request, HTTPException
from fastapi.responses import JSONResponse,FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError
from backend.database.store import Store,ROOT
from backend.services.intelligence import Intelligence

def create_app(store=None):
    from backend.genai.redaction import install_redaction
    install_redaction()
    @asynccontextmanager
    async def lifespan(app):
        app.state.store=store or Store()
        from backend.database.retrieval_mart import attach
        attach(app.state.store)
        app.state.service=Intelligence(app.state.store)
        from backend.agents.chatbot import RegInsightChatAgent
        app.state.chatbot=RegInsightChatAgent(app.state.service)
        from backend.workflows.factory import create_workflows
        import httpx
        try:
            app.state.workflows=create_workflows(app.state.service)
        except (httpx.HTTPError, RuntimeError):
            # Deterministic analytics remain available when local model startup fails.
            app.state.workflows=None
        try:yield
        finally:
            from backend.cache.redis_cache import get_cache
            get_cache().close()
            get_cache.cache_clear()
    app=FastAPI(title='Regulatory Inspection Insights Assistant',version='1.0.0',lifespan=lifespan)
    from backend.api.security import install_security
    install_security(app)
    import time
    @app.middleware('http')
    async def retrieval_timing(request,call_next):
        start=time.perf_counter()
        response=await call_next(request)
        response.headers['Server-Timing']=f'app;dur={(time.perf_counter()-start)*1000:.2f}'
        return response

    from pydantic import ValidationError
    @app.exception_handler(ValidationError)
    async def invalid_output(request,exc):return JSONResponse(status_code=500,content={'detail':'Stored or generated output failed validation.'})
    @app.exception_handler(ValueError)
    async def invalid(request,exc): return JSONResponse(status_code=400,content={'detail':str(exc)})
    @app.exception_handler(SQLAlchemyError)
    async def db_error(request,exc): return JSONResponse(status_code=503,content={'detail':'Database unavailable. Check the database connection and retry.'})

    import psycopg
    from psycopg_pool import PoolTimeout
    app.add_exception_handler(psycopg.Error,db_error)
    app.add_exception_handler(PoolTimeout,db_error)

    def service(request): return request.app.state.service

    @app.get('/api/health')
    def health(request:Request):
        s=service(request)
        return {'status':'ok','database':s.store.dialect,'warning':s.store.warning,'dataset_loaded':s.store.info() is not None}

    @app.get('/api/cache/status')
    def cache_status():
        from backend.cache.redis_cache import get_cache
        return get_cache().status()

    @app.get('/api/dashboard')
    def dashboard(request:Request,company:str|None=None,country:str|None=None,product_type:str|None=None,project_area:str|None=None,classification:str|None=None,year:int|None=None):
        return service(request).dashboard(company=company,country=country,product_type=product_type,project_area=project_area,classification=classification,year=year)

    @app.get('/api/inspections')
    def inspections(request:Request,company:str|None=None,site:str|None=None,fei_number:str|None=None,country:str|None=None,product_type:str|None=None,project_area:str|None=None,classification:str|None=None,year:int|None=None,limit:int=Query(25,ge=1,le=200),offset:int=Query(0,ge=0)):
        s=service(request); s.info()
        filters=dict(company=company,site=site,fei_number=fei_number,country=country,product_type=product_type,project_area=project_area,classification=classification,year=year)
        total=s.store.search(count_only=True,**filters)
        records=s.store.search(limit=limit,offset=offset,**filters)
        return {'total':total,'records':records,'limit':limit,'offset':offset}

    @app.get('/api/companies')
    def companies(request:Request,search:str|None=None): return service(request).entities('company',search=search)

    @app.get('/api/sites')
    def sites(request:Request,company:str|None=None): return service(request).entities('site',company=company)

    @app.get('/api/profile')
    def profile(request:Request,company:str|None=None,site:str|None=None,fei_number:str|None=None):
        if not any([company,site,fei_number]): raise ValueError('Select a company, site or FEI.')
        return service(request).profile(company=company,site=site,fei_number=fei_number)

    @app.get('/api/risk')
    def risk(request:Request,company:str|None=None,site:str|None=None,fei_number:str|None=None):
        return service(request).risk(company=company,site=site,fei_number=fei_number)

    @app.get('/api/trends')
    def trends(request:Request,company:str|None=None,site:str|None=None,fei_number:str|None=None,theme:str|None=None,classification:str|None=None,country:str|None=None,product_type:str|None=None,project_area:str|None=None,start_year:int|None=None,end_year:int|None=None):
        return service(request).trend(company=company,site=site,fei_number=fei_number,theme=theme,classification=classification,country=country,product_type=product_type,project_area=project_area,start_year=start_year,end_year=end_year)

    @app.get('/api/recurrence')
    def recurrence(request:Request,company:str|None=None,site:str|None=None,fei_number:str|None=None,country:str|None=None,product_type:str|None=None,year:int|None=None,group_by:str|None=None):
        return service(request).recurrence(company=company,site=site,fei_number=fei_number,country=country,product_type=product_type,year=year,group_by=group_by)

    @app.get('/api/data-quality')
    def quality(request:Request,kind:str=Query('rejected',pattern='^(rejected|duplicates)$'),offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=200)):
        info=service(request).info()
        return {**{k:v for k,v in info.items() if k not in ['dashboard_cache','rejected','duplicates']},
                'review_kind':kind,'review_total':len(info.get(kind,[])),'review_records':info.get(kind,[])[offset:offset+limit]}

    @app.get('/api/evidence/{analysis_id}')
    def evidence(request:Request,analysis_id:str,offset:int=Query(0,ge=0),limit:int=Query(25,ge=1,le=200)):
        item=service(request).store.get_evidence(analysis_id)
        if item is None: raise HTTPException(404,'Evidence analysis not found')
        records=item.get('records',[])
        return {**item,'records':records[offset:offset+limit],'record_count':len(records),'offset':offset}

    from backend.api.ai import router as ai_router
    app.include_router(ai_router)
    from backend.api.agent import router as agent_router
    app.include_router(agent_router)
    from backend.api.dashboard_assistant import router as dashboard_router
    app.include_router(dashboard_router)
    from backend.api.chatbot import router as chatbot_router
    app.include_router(chatbot_router)
    from backend.api.alerts import router as alerts_router
    app.include_router(alerts_router)
    from backend.api.benchmarks import router as benchmark_router
    app.include_router(benchmark_router)

    from backend.api.observation_workspace import router as observations_router
    app.include_router(observations_router)

    from backend.api.observation_intelligence import router as intelligence_router
    app.include_router(intelligence_router)

    from backend.api.qc import router as qc_router
    app.include_router(qc_router)

    from backend.api.workspace import router as website_router
    app.include_router(website_router)
    from backend.api.workflows import router as workflows_router
    app.include_router(workflows_router)

    dist=ROOT/'frontend/dist'
    if dist.exists():
        app.mount('/assets',StaticFiles(directory=dist/'assets'),name='assets')
    @app.get('/')
    def frontend():
        if not (dist/'index.html').exists(): return JSONResponse(status_code=503,content={'detail':'Frontend build missing. Run npm install and npm run build in frontend.'})
        return FileResponse(dist/'index.html')
    return app

app=create_app()
