from fastapi import APIRouter, Request, HTTPException
from pydantic import ValidationError
from backend.semantic.catalog import catalog
from backend.semantic.models import QueryRequest, QueryResponse
from backend.services.dashboard_insights import DashboardInsights
router=APIRouter()
@router.get('/api/semantic/catalog')
def semantic_catalog():return catalog()
@router.post('/api/agent/dashboard-query',response_model=QueryResponse)
def dashboard_query(request:Request,body:QueryRequest):
    try:return DashboardInsights(request.app.state.service).query(body)
    except ValidationError as exc:
        raise HTTPException(400,'Unsupported query plan: '+ '; '.join(e['msg'] for e in exc.errors())) from None
