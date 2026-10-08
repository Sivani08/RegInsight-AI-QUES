"""Bounded SQL dashboard queries shared by the dashboard and conversational UI.

The existing calculate_risk function remains the sole risk implementation.
Scoped risk summaries stream one site's history at a time into a derived mart.
"""
import hashlib
import json
import threading
from datetime import date, timedelta
from itertools import groupby
from sqlalchemy import select, func, case, cast, Integer, Table, Column, String, Float, JSON, delete
from backend.database.store import inspections as t, metadata
from backend.analytics.metrics import ratio
from backend.risk.engine import calculate_risk

scoped = Table('dashboard_scope_sites', metadata,
    Column('scope', String, primary_key=True), Column('site_key', String, primary_key=True),
    Column('score', Float, index=True), Column('band', String, index=True), Column('payload', JSON))
scope_runs = Table('dashboard_scope_runs', metadata, Column('scope', String, primary_key=True), Column('created', String))
lock = threading.Lock()
BANDS = ['LOW','MODERATE','HIGH','CRITICAL','INSUFFICIENT DATA']

def where(filters,table=None):
    t=table if table is not None else globals()['t']
    clauses = []
    fields = {'company':'company_key','site':'site_key','fei_number':'fei_number',
              'country':'country','product_type':'product_type','project_area':'project_area',
              'classification':'classification','year':'inspection_year'}
    for key, value in filters.items():
        if value is None or value == '': continue
        if key in fields:
            if key == 'company': value = value.strip().casefold()
            clauses.append(t.c[fields[key]] == value)
        elif key in ('start_year','end_year'):
            clauses.append(t.c.inspection_year >= value if key == 'start_year' else t.c.inspection_year <= value)
        elif key in ('start_date','end_date','inspection_type'):
            column = t.c.payload['inspection_date' if key != 'inspection_type' else key].as_string()
            clauses.append(column >= str(value) if key == 'start_date' else column <= str(value) if key == 'end_date' else column == value)
        else: raise ValueError('Unsupported inspection filter: ' + key)
    return clauses

def aggregate(store, as_of, filters, by_year=False):
    from backend.database.retrieval_mart import table_for
    t=table_for(store)
    # Reuse the canonical materialized portfolio instead of rescanning large evidence JSON.
    info=store.info() or {}
    if not any(filters.values()) and info.get('dashboard_cache'):
        if by_year:return info['dashboard_cache']['trend']
        return {**info['dashboard_cache']['metrics'],'unique_sites':info.get('entity_counts',{}).get('site',0)}
    def value(k): return cast(t.c.payload[k].as_string(), Integer)
    def count_if(condition): return func.coalesce(func.sum(case((condition,1), else_=0)),0)
    citation = value('citation_indicator')
    obs = value('observation_count')
    dt = t.c.payload['inspection_date'].as_string()
    dated = dt.is_not(None) & (dt != '')
    cutoff = (date.fromisoformat(as_of)-timedelta(days=365)).isoformat()
    columns = [func.count().label('total_inspections'),func.sum(citation).label('citation_positive'),
        func.count(citation).label('citation_known'),func.count(obs).label('observations_known'),
        func.sum(obs).label('observation_sum'),func.count(func.distinct(t.c.site_key)).label('unique_sites'),
        count_if(dated).label('dated_inspections'),
        func.count(func.distinct(case((dated,t.c.inspection_year),else_=None))).label('dated_years'),
        count_if(dated & (dt >= cutoff) & (dt <= as_of)).label('recent_inspections'),
        func.sum(value('posted_citation_indicator')).label('posted_citation_inspections'),
        func.sum(value('available_citation_count')).label('available_citation_rows')]
    columns += [count_if(t.c.classification == k).label(k) for k in ('OAI','VAI','NAI')]
    columns += [count_if(t.c.classification.is_(None) | (t.c.classification == '') | (t.c.classification == 'Unknown')).label('Unknown')]
    if by_year: columns.insert(0,t.c.inspection_year.label('year'))
    stmt = select(*columns).where(*where(filters,t))
    if by_year: stmt = stmt.where(t.c.inspection_year.is_not(None)).group_by(t.c.inspection_year).order_by(t.c.inspection_year)
    with store.engine.connect() as conn: rows = [dict(r) for r in conn.execute(stmt).mappings()]
    for r in rows:
        r['classification_known'] = sum(r[k] for k in ('NAI','VAI','OAI'))
        r['citation_rate'] = ratio(r['citation_positive'] or 0,r['citation_known'])
        r['oai_rate'] = ratio(r['OAI'],r['classification_known'])
        r['average_observations'] = ratio(r.pop('observation_sum') or 0,r['observations_known'])
        r['inspection_frequency'] = ratio(r['dated_inspections'],r.pop('dated_years'))
        r['frequency_unit'] = 'inspections per observed calendar year'
        if by_year: r['partial_year'] = str(r['year']) == as_of[:4] and as_of[5:] != '12-31'
    return rows if by_year else rows[0]

def site_scope(service, filters):
    """Cache exact scope; no LLM values, no cross-scope reuse and no in-memory ranking."""
    from backend.services.mart import entities_table
    from backend.database.retrieval_mart import table_for
    t=table_for(service.store)
    info = service.info()
    if not any(filters.values()) and info.get('mart_ready'):
        if info.get('dashboard_cache',{}).get('methodology') != service.config:
            raise ValueError('Risk methodology changed; rebuild the materialized summaries.')
        return entities_table, [entities_table.c.kind == 'site']
    key = hashlib.sha256(json.dumps([info['dataset_id'],service.config,filters],sort_keys=True,default=str).encode()).hexdigest()
    with lock, service.store.engine.begin() as conn:
        if not conn.execute(select(scope_runs.c.scope).where(scope_runs.c.scope==key)).first():
            fields=['company_name','site_name','inspection_date','citation_indicator','observation_count',
                    'observation_text','posted_citation_indicator','available_citation_count']
            columns=[t.c[k] for k in ['inspection_id','company_key','site_key','fei_number','country','classification','inspection_year']]
            columns += [t.c.payload[k].as_string().label(k) for k in fields]
            stream = conn.execute(select(*columns).where(*where(filters,t)).order_by(t.c.site_key).execution_options(stream_results=True)).mappings()
            for site, group in groupby(stream,lambda r:r['site_key']):
                records = []
                for record in group:
                    r=dict(record)
                    for f in ('citation_indicator','observation_count','posted_citation_indicator','available_citation_count'):
                        if r[f] is not None:r[f]=int(r[f])
                    records.append(r)
                first=max(records,key=lambda r:r['inspection_date'] or '')
                risk=calculate_risk(records,info['as_of'],service.config)
                payload={'key':site or 'unknown','company_name':first['company_name'],'site_name':first['site_name'],
                         'fei_number':first['fei_number'],'country':first['country'],'risk':risk}
                conn.execute(scoped.insert().values(scope=key,site_key=site or 'unknown',score=risk['score'],band=risk['band'],payload=payload))
            conn.execute(scope_runs.insert().values(scope=key,created=__import__('datetime').datetime.now().isoformat()))
            old=list(conn.execute(select(scope_runs.c.scope).order_by(scope_runs.c.created.desc()).offset(32)).scalars())
            if old:
                conn.execute(delete(scoped).where(scoped.c.scope.in_(old)))
                conn.execute(delete(scope_runs).where(scope_runs.c.scope.in_(old)))
    return scoped,[scoped.c.scope==key]

def ranked_sites(service, filters, limit=10, offset=0, band=None):
    table, conditions=site_scope(service,filters)
    if band: conditions += [table.c.band==band]
    key=table.c.entity_key if 'entity_key' in table.c else table.c.site_key
    with service.store.engine.connect() as conn:
        total=conn.execute(select(func.count()).select_from(table).where(*conditions)).scalar_one()
        rows=list(conn.execute(select(table.c.payload).where(*conditions).order_by(table.c.score.desc().nulls_last(),key).limit(limit).offset(offset)).scalars())
    return rows,total

def risk_distribution(service,filters):
    table, conditions=site_scope(service,filters)
    with service.store.engine.connect() as conn:
        counts=dict(conn.execute(select(table.c.band,func.count()).where(*conditions).group_by(table.c.band)).all())
    return {k:counts.get(k,0) for k in BANDS}

def dashboard(service,filters):
    from backend.cache.redis_cache import get_cache
    from backend.cache.retrieval import inspection_identity
    cache=get_cache()
    return cache.remember(cache.key('dashboard',[inspection_identity(service),filters]),lambda:_dashboard(service,filters))

def _dashboard(service,filters):
    info=service.info()
    sites,total=ranked_sites(service,filters,100)
    bands=risk_distribution(service,filters)
    totals=aggregate(service.store,info['as_of'],filters)
    trend=aggregate(service.store,info['as_of'],filters,True)
    from backend.analytics.graph_insights import graph_insights
    return {'metrics':totals,'sites':sites,'graph_insights':graph_insights(totals,trend,bands,info['as_of']),
            'site_total':total,'risk_distribution':bands,'attention_sites':bands['HIGH']+bands['CRITICAL'],
            'trend':trend,'recurrence':info.get('dashboard_cache',{}).get('recurrence',[]) if not any(filters.values()) else service.recurrence(**filters),
            'methodology':service.config,'info':{k:v for k,v in info.items() if k not in ('dashboard_cache','rejected','duplicates')}}
