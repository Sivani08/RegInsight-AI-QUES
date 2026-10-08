"""Typed query-loop service. Narrative composition cannot replace numerical facts."""
import copy
import json
import logging
import time
import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from backend.database.store import inspections
from backend.analytics import dashboard_queries as queries
from backend.semantic.catalog import METRICS, VERSION
from backend.semantic.models import QueryRequest, QueryResponse, Layers, Insight, Context
from backend.semantic.planner import plan

FIELD_MAP={'citation_positive_inspections':'citation_positive','posted_citations':'available_citation_rows',
           'nai_count':'NAI','vai_count':'VAI','oai_count':'OAI'}
OBS_FOCUS={'observation_intelligence','recurring_risk_signals'}

def canonical(values):
    return {**values,**{k:values.get(v) for k,v in FIELD_MAP.items()}}

def observation_insights(query):
    from backend.api import workspace
    from data_engineering.intelligence_sources import db
    from backend.services import observation_intelligence as intelligence
    f=query.filters.model_dump(exclude_none=True,mode='json')
    rid,joined,args=workspace.cohort(dataset=f.get('dataset','real'),severity=f.get('severity'),year=f.get('year'),theme=f.get('theme'))
    for key,column in [('company','company'),('site','site'),('fei_number','site'),('semantic_group','group_id')]:
        if f.get(key):joined+=' AND lower(o.'+column+')=lower(%s)';args.append(f[key])
    if f.get('start_year'):joined+=' AND o.year>=%s';args.append(f['start_year'])
    if f.get('end_year'):joined+=' AND o.year<=%s';args.append(f['end_year'])
    with db(workspace.DB) as c:
        workspace.review_table(c)
        stats=dict(c.execute('SELECT count(*) observation_count,count(DISTINCT o.inspection_id) distinct_inspections'+joined,args).fetchone())
        severity=[dict(r) for r in c.execute('SELECT o.severity,count(*) count'+joined+' GROUP BY o.severity ORDER BY count DESC',args)]
        themes=[dict(r) for r in c.execute('SELECT o.theme,count(DISTINCT o.inspection_id) inspections,count(*) observations'+joined+" AND o.theme!='Unclassified' GROUP BY o.theme ORDER BY inspections DESC,o.theme LIMIT %s OFFSET %s",args+[query.limit,query.offset])]
        recurring=c.execute('SELECT count(*) FROM (SELECT o.theme'+joined+" AND o.theme!='Unclassified' GROUP BY o.theme HAVING count(DISTINCT o.inspection_id)>1)",args).fetchone()[0]
        repeats=c.execute('SELECT coalesce(sum(n-1),0) FROM (SELECT count(DISTINCT o.inspection_id) n'+joined+" AND o.theme!='Unclassified' GROUP BY o.theme HAVING count(DISTINCT o.inspection_id)>1)",args).fetchone()[0]
        review=c.execute('SELECT count(*)'+joined+" AND NOT EXISTS (SELECT 1 FROM website_reviews w WHERE w.run_id=o.run_id AND w.observation_id=o.id AND w.revision=(SELECT max(w2.revision) FROM website_reviews w2 WHERE w2.run_id=o.run_id AND w2.observation_id=o.id) AND (w.payload::jsonb ->> 'action') IN ('Approve','Modify'))",args).fetchone()[0]
        trend=[dict(r) for r in c.execute('SELECT o.year,count(*) observation_count,count(DISTINCT o.inspection_id) distinct_inspections'+joined+' AND o.year IS NOT NULL GROUP BY o.year ORDER BY o.year',args)]
        detail_scope=joined
        if 'review_required_count' in query.metrics:
            detail_scope+=" AND NOT EXISTS (SELECT 1 FROM website_reviews w WHERE w.run_id=o.run_id AND w.observation_id=o.id AND w.revision=(SELECT max(w2.revision) FROM website_reviews w2 WHERE w2.run_id=o.run_id AND w2.observation_id=o.id) AND (w.payload::jsonb ->> 'action') IN ('Approve','Modify'))"
        ids=[r[0] for r in c.execute('SELECT o.id'+detail_scope+' ORDER BY o.severity_rank DESC,o.id LIMIT %s OFFSET %s',args+[min(query.limit,10),query.offset])]
        if 'site' in query.dimensions:
            themes=[dict(r) for r in c.execute('SELECT o.site,count(DISTINCT o.inspection_id) inspections,count(*) observations'+joined+' GROUP BY o.site HAVING count(DISTINCT o.inspection_id)>1 ORDER BY inspections DESC,o.site LIMIT %s OFFSET %s',args+[query.limit,query.offset])]
    evidence=[]
    for oid in ids:
        record=intelligence.tags(run_id=rid,observation_id=oid,path=workspace.DB,limit=1).records[0]
        evidence.append({'observation_id':oid,'inspection_id':record.inspection_id,'source_file':record.source_file,
          'source_row':record.source_row,'theme':record.tag.theme,'severity':record.tag.severity,'semantic_group':record.observation_group_id,'quote':record.tag.evidence_quote[:1200]})
    rows=themes if query.focus=='recurring_risk_signals' else evidence
    if query.intent=='trend_analysis':rows=trend[-query.limit:]
    return {'metrics':{**stats,'recurring_themes':recurring,'recurrence_count':repeats,'review_required_count':review,
                      'severity_distribution':severity},'rows':rows,'trend':trend,'evidence':evidence,'run_id':rid,'total':review if 'review_required_count' in query.metrics else stats['observation_count']}

class DashboardInsights:
    def __init__(self,service):self.service=service

    def get_inspection_activity(self,filters):
        return queries.aggregate(self.service.store,self.service.info()['as_of'],filters,True)
    def get_classification_distribution(self,filters):
        return canonical(queries.aggregate(self.service.store,self.service.info()['as_of'],filters))
    def get_citation_oai_trend(self,filters):return self.get_inspection_activity(filters)
    def get_risk_distribution(self,filters):return queries.risk_distribution(self.service,filters)
    def get_ranked_sites(self,filters,limit=10,offset=0,band=None):return queries.ranked_sites(self.service,filters,limit,offset,band)
    def get_overall_insights(self,filters):return self.get_classification_distribution(filters)
    def get_recurring_risk_signals(self,query):return observation_insights(query)
    def get_observation_dashboard_insights(self,query):return observation_insights(query)

    def execute(self,query):
        # Review-dependent observation queries retain their existing validation path.
        if query.focus in OBS_FOCUS:return observation_insights(query)
        from backend.cache.redis_cache import get_cache
        from backend.cache.retrieval import inspection_identity
        cache=get_cache()
        return cache.remember(cache.key('query-plan',[inspection_identity(self.service),query.model_dump(mode='json')]),lambda:self._execute(query))

    def _execute(self,query):
        f=query.filters.model_dump(exclude_none=True,mode='json')
        if query.focus in OBS_FOCUS:return observation_insights(query)
        band=f.pop('risk_band',None)
        facts=self.get_overall_insights(f)
        rows=[];trend=[];total=facts['total_inspections']
        if query.intent=='trend_analysis' or query.focus in ('inspection_activity','citation_oai_trend'):
            trend=self.get_inspection_activity(f);rows=trend[-query.limit:]
            if 'risk_score' in query.metrics and any(f.get(k) for k in ('site','company','fei_number')):
                trend=self.service.trend(**f);rows=trend[-query.limit:]
        if query.focus in ('sites_to_investigate','risk_distribution') or query.focus=='overall_dashboard':
            distribution=self.get_risk_distribution(f)
            facts.update(risk_distribution=distribution,high_risk_sites=distribution['HIGH'],critical_risk_sites=distribution['CRITICAL'])
            ranked,total=self.get_ranked_sites(f,query.limit,query.offset,band)
            if query.intent!='trend_analysis':rows=ranked
            if any(m in query.metrics for m in ('risk_score','risk_band')) and any(f.get(k) for k in ('site','company','fei_number')):
                # Scope may be company-wide. Existing engine owns every factor and score.
                risk=self.service.risk(**f)
                facts.update(risk_score=risk['score'],risk_band=risk['band'],risk_components=risk['components'],coverage_pct=risk['coverage_pct'])
        if query.focus=='data_quality':
            info=self.service.info()
            facts['dataset_quality']={k:info.get(k) for k in ('valid_records','rejected_records','duplicate_records','data_completeness_pct')}
        # Evidence stays bounded. All metrics were computed before reading detailed records.
        stmt=select(inspections.c.inspection_id,inspections.c.payload).where(*queries.where(f)).order_by(inspections.c.inspection_year.desc(),inspections.c.inspection_id).limit(min(query.limit,10)).offset(query.offset)
        with self.service.store.engine.connect() as c:
            evidence=[]
            for iid,r in c.execute(stmt):
                provenance=json.loads(r.get('source_record') or '{}')
                evidence.append({'inspection_id':iid,'company':r.get('company_name'),'site':r.get('site_name'),
                    'classification':r.get('classification'),'inspection_date':r.get('inspection_date'),
                    'source_file':r.get('source_file') or provenance.get('inspection_file'),'source_row':r.get('source_row'),
                    'source_reference':r.get('source_reference'),'quote':(r.get('observation_text') or '')[:1200]})
        if query.intent=='detail':rows=evidence;total=facts['total_inspections']
        return {'metrics':facts,'rows':rows,'trend':trend,'evidence':evidence,'run_id':None,'total':total}

    def query(self,request:QueryRequest):
        start=time.perf_counter(); timing={}
        previous=self.service.store.get_evidence(request.context.analysis_id) if request.context.analysis_id else None
        if previous and previous.get('kind')!='dashboard':previous=None
        info=self.service.info()
        if previous and previous.get('dataset_id')!=info['dataset_id']:previous=None
        with self.service.store.engine.connect() as c:
            latest=c.execute(select(func.max(inspections.c.inspection_year)).where(*queries.where({k:v for k,v in request.filters.model_dump(exclude_none=True,mode='json').items() if k not in ('theme','severity','semantic_group','dataset','grain','risk_band')}))).scalar_one_or_none()
        tick=time.perf_counter();timing['context_resolution_ms']=(tick-start)*1000
        query=plan(request,previous,latest)
        timing['semantic_resolution_ms']=(time.perf_counter()-tick)*1000
        tick=time.perf_counter()
        # Revalidate the plan at the execution boundary, including constructed objects.
        query=type(query).model_validate(query.model_dump())
        timing['planning_ms']=(time.perf_counter()-tick)*1000
        tick=time.perf_counter(); result=self.execute(query);timing['analytics_ms']=(time.perf_counter()-tick)*1000
        tick=time.perf_counter()
        facts=copy.deepcopy(result['metrics']);patterns={}
        trend=result['trend']
        if len(trend)>=2:
            a,b=trend[-2:]
            patterns={'previous_year':a['year'],'latest_year':b['year'],'partial_year':b.get('partial_year',False)}
            for key in ('total_inspections','observation_count','citation_rate','oai_rate','risk_score','OAI','VAI','NAI'):
                if a.get(key) is not None and b.get(key) is not None:
                    patterns[key+('_percentage_point_change' if key.endswith('_rate') else '_change')]=round((b[key]-a[key])*(100 if key.endswith('_rate') else 1),6)
            if 'total_inspections' in b:patterns['highest_volume_year']=max(trend,key=lambda r:r.get('total_inspections',0))['year']
        limitations=['Risk is a prioritization heuristic, not an FDA determination.','Reported associations do not establish causes.']
        if query.focus in OBS_FOCUS:limitations+=['Observation snapshot scope is separate from the inspection portfolio.','Text recurrence is not proof of repeated regulatory violations.']
        if facts.get('citation_known')==0:limitations+=['Citation rate unavailable: no known citation-indicator denominator. Posted citations are not a substitute.']
        if patterns.get('partial_year'):limitations+=['Latest year is partial. Prior-year comparisons are descriptive and not matched year-to-date comparisons.']
        if query.focus=='data_quality':limitations+=['Dataset quality measures describe the entire imported dataset; inspection totals respect the selected filters.']
        if facts.get('coverage_pct') is not None:limitations+=[f"Risk factor coverage is {facts['coverage_pct']}%; unavailable factors are excluded, not treated as zero."]
        eid=uuid.uuid4().hex
        layers=Layers(scope={'focus':query.focus,'filters':query.filters.model_dump(exclude_none=True,mode='json'),
            'dataset_id':info['dataset_id'],'run_id':result['run_id'],'as_of':info['as_of'],
            'grain':'observation' if query.focus in OBS_FOCUS else 'inspection','source_label':info['data_label']},
            metrics=facts,patterns=patterns,context={'interpretation':'Observed facts and deterministic comparisons; no causal attribution.','explanation_mode':'deterministic templates'},
            evidence_and_limitations={'evidence_id':eid,'methodology_version':self.service.config['version'],
              'semantic_version':VERSION,'definitions':{m:METRICS[m][0] for m in query.metrics},
              'denominators':{k:facts.get(k) for k in ('citation_known','classification_known')},
              'source_files':[r.get('file') for r in info.get('source_files',[])],
              'tools':['existing calculate_risk','dashboard SQL aggregates','observation snapshot SQL'],
              'limitations':limitations,'records':result['evidence'],'evidence_page_size':len(result['evidence'])})
        timing['evidence_ms']=(time.perf_counter()-tick)*1000
        tick=time.perf_counter()
        response=self.compose(request,query,layers,result,eid)
        validate_numeric(response,facts,patterns)
        self.service.store.save_evidence(eid,{'kind':'dashboard','analysis_id':eid,'dataset_id':info['dataset_id'],
            'created_at':datetime.now(timezone.utc).isoformat(),'question':request.question,
            'semantic_plan':query.model_dump(mode='json'),'dashboard_filters':request.filters.model_dump(exclude_none=True,mode='json'),
            'result_references':[{'key':r['key'],'company':r.get('company_name')} for r in result['rows'] if 'key' in r][:50],
            'theme_references':[r['theme'] for r in result['rows'] if 'theme' in r][:50],
            'group_references':[r['semantic_group'] for r in result['evidence'] if 'semantic_group' in r][:10],
            'metrics':facts,'patterns':patterns,'records':result['evidence'],'limitations':limitations})
        timing['response_composition_ms']=(time.perf_counter()-tick)*1000
        timing['total_ms']=(time.perf_counter()-start)*1000
        logging.getLogger(__name__).info(json.dumps({'event':'dashboard_query','focus':query.focus,'intent':query.intent,'timing':timing}))
        return response

    def compose(self,request,query,layers,result,eid):
        f=layers.metrics
        headline='The selected portfolio contains '+str(f.get('total_inspections',f.get('observation_count',0)))+' '+('observations.' if query.focus in OBS_FOCUS else 'inspections.')
        if query.intent=='ranking':headline='Sites ranked by the existing deterministic risk score.'
        elif query.intent=='risk_explanation':headline='The selected scope has a '+str(f.get('risk_band','unavailable')).lower()+' risk assessment.'
        elif query.intent=='trend_analysis':headline='Period changes are calculated from the selected source records.'
        elif query.intent=='evidence':headline='These source references support the current analytical scope.'
        elif query.intent=='methodology':headline='The calculation uses the metric definitions and denominators below.'
        elif query.focus=='classification_distribution':headline='Inspection classifications in the selected scope.'
        insights=[Insight(type='fact',statement=METRICS[m][0],metrics={m:f.get(m)}) for m in query.metrics]
        if query.focus=='data_quality':insights.append(Insight(type='fact',statement='Quality of the complete imported dataset',metrics={'dataset_quality':f['dataset_quality']}))
        if layers.patterns:insights.append(Insight(type='pattern',statement='Changes between the latest two available periods in scope.',metrics=layers.patterns))
        if query.intent not in ('evidence','methodology','risk_explanation','detail') and query.focus in ('inspection_activity','classification_distribution','citation_oai_trend','risk_distribution'):
            from backend.analytics.graph_insights import graph_insights
            summary=graph_insights(f,result['trend'],f.get('risk_distribution'),layers.scope['as_of']).get(query.focus)
            if summary:
                headline=summary['headline']
                insights.insert(0,Insight(type='fact',statement=summary['detail'],metrics={}))
        questions=['How did you calculate that%s','What evidence supports that%s']
        if query.focus=='sites_to_investigate':questions=['Why is the first one high%s','Show the inspections.','How did you calculate that%s'] if query.intent!='risk_explanation' else ['Show the inspections.','What evidence supports that%s','How did you calculate that%s']
        elif query.focus in OBS_FOCUS:questions=['Which observations require review%s','What is the severity distribution%s','What evidence supports that%s']
        else:questions=['Which sites have the highest risk%s','What changed from last year%s','How did you calculate that%s']
        return QueryResponse(question=request.question,semantic_plan=query,headline=headline,insights=insights,layers=layers,
              supporting_data=result['rows'][:query.limit],suggested_questions=questions,context=Context(analysis_id=eid),
              evidence_id=eid,total=result['total'],limit=query.limit,offset=query.offset)

def validate_numeric(response,authoritative,patterns):
    if response.layers.metrics != authoritative or response.layers.patterns != patterns:
        raise ValueError('Response facts failed authoritative validation')
    for insight in response.insights:
        source=patterns if insight.type=='pattern' else authoritative
        if any(value != source.get(key) for key,value in insight.metrics.items()):
            raise ValueError('Response insight substituted an unsupported value')
