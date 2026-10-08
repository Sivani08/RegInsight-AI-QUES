import io,csv,json
from fastapi import APIRouter,Query,HTTPException,Request
from backend.api.identity import reviewer
from fastapi.responses import FileResponse,Response
from pydantic import BaseModel,ConfigDict,Field
from typing import Literal
from backend.services import qc_data as d,qc_signals as s,knowledge as k,qc_connections as connections
router=APIRouter(prefix='/api/qc')
class CSVRequest(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=1,max_length=200)
    kind:Literal['real','demo']
    csv_text:str=Field(min_length=1,max_length=2000000)
@router.get('/datasets')
def datasets():return d.datasets()
@router.post('/import')
def import_json(body:d.ImportRequest):return d.ingest(body,method='api_push')
@router.post('/import-csv')
def import_csv(body:CSVRequest):return d.csv_import(body.csv_text,body.name,body.kind)
@router.get('/connections')
def connection_catalog():return connections.catalog()
@router.post('/connections/{identifier}/sync')
def sync(identifier:str):return connections.sync(identifier)
@router.get('/signals')
def signals(dataset_id:str,study:str|None=None,as_of:str|None=None):return s.analyze(dataset_id,study,as_of)
@router.get('/audit')
def audit(dataset_id:str):return d.audit(dataset_id)
@router.post('/review')
def review(body:d.ReviewRequest,request:Request):
    body=body.model_copy(update={'actor':reviewer(request).user_id})
    matches=[x for x in s.analyze(body.dataset_id)['signals'] if x['id']==body.signal_id]
    if not matches:raise HTTPException(400,'Signal is not present in the current dataset assessment')
    return d.review(body,matches[0])
@router.get('/export')
def export(dataset_id:str,study:str|None=None):
    _,rows=d.rows(dataset_id,study);out=io.StringIO();fields=list(d.QCRecord.model_fields)
    writer=csv.DictWriter(out,fieldnames=fields,extrasaction='ignore');writer.writeheader()
    for r in rows:
        safe={k:("'"+v if isinstance(v,str) and v[:1] in '=+-@' else v) for k,v in r.items()};writer.writerow(safe)
    return Response(out.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="qc-records.csv"'})
@router.get('/knowledge')
def knowledge(query:str=Query('',max_length=500),limit:int=Query(10,ge=1,le=30)):
    return {'sources':k.sources(),'matches':k.search(query,limit)}
@router.get('/knowledge/{source_id}')
def source(source_id:str):
    matches=[x for x in k.sources() if x['id']==source_id]
    if not matches:raise HTTPException(404,'Unknown source')
    path=(d.ROOT/matches[0]['path']).resolve();base=(d.ROOT/'data/knowledge/sources').resolve()
    if not path.is_relative_to(base):raise HTTPException(400,'Invalid source path')
    return FileResponse(path,filename=path.name)
