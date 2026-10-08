"""Operator-configured, bounded JSON API imports; no URLs accepted from UI users."""
import json,os,re
from urllib.parse import urlsplit
import httpx
from backend.services import qc_data as data
CONFIG=data.ROOT/'config/qc_connections.json'
def configs():return json.loads(CONFIG.read_text(encoding='utf-8-sig')).get('connections',[])
def catalog():return [{'id':c['id'],'name':c.get('name',c['id']),'enabled':c.get('enabled',False),'kind':c['kind'],'method':'API pull','credential_configured':bool(os.getenv(c.get('token_env',''))) if c.get('token_env') else None} for c in configs()]
def sync(identifier):
    matches=[c for c in configs() if c['id']==identifier]
    if not matches:raise ValueError('Unknown configured connection')
    cfg=matches[0]
    if not cfg.get('enabled'):raise ValueError('Connection disabled')
    url=cfg['url'];parts=urlsplit(url)
    if parts.scheme!='https' or not parts.hostname or parts.username or parts.password or parts.query or parts.fragment:raise ValueError('Use a configured HTTPS endpoint without credentials or query secrets')
    headers={}
    if cfg.get('token_env'):
        if not re.fullmatch('[A-Z][A-Z0-9_]+',cfg['token_env']):raise ValueError('Invalid credential environment variable name')
        token=os.getenv(cfg['token_env'])
        if not token:raise ValueError('Connection credential is not configured')
        headers['Authorization']='Bearer '+token
    try:
        with httpx.Client(timeout=15,follow_redirects=False) as client,client.stream('GET',url,headers=headers) as response:
            response.raise_for_status();raw=bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw)>2000000:raise ValueError('API payload exceeds 2 MB')
        payload=json.loads(raw)
        if not isinstance(payload,list):raise ValueError('API must return an array of QC records')
        body=data.ImportRequest(name=cfg.get('name',identifier),kind=cfg['kind'],records=[data.QCRecord.model_validate(r) for r in payload])
    except (httpx.HTTPError,ValueError,TypeError) as e:raise ValueError('API import failed validation or transport: '+type(e).__name__) from None
    return data.ingest(body,method='api_pull',source=identifier)
