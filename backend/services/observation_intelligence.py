"""Snapshot-based all-source classification/cache and SQL numerical authority."""
import json,os,time,uuid,hashlib
from pathlib import Path
from datetime import datetime,timezone
from data_engineering.intelligence_sources import DB,db
from backend.genai.classifier import Classifier
from backend.genai.contracts import ObservationTag,ObservationRecord,TagsPage,ThemeMetric,MetricsPage
from backend.genai.classification_prompt import PROMPT_VERSION,NOTICE
from backend.analytics.intelligence_taxonomy import VERSION
from backend.analytics.observation_groups import Grouper
from backend.cache.snapshots import snapshot_cache
from backend.cache.redis_cache import get_cache
SEVERITY={'Low':.25,'Medium':.5,'High':.75,'Critical':1.,'Unclassified':0.}
def latest(path=DB):
    with db(path) as c:
        row=c.execute("SELECT id,payload FROM runs WHERE (payload::jsonb ->> 'status')='completed' ORDER BY storage_sequence DESC LIMIT 1").fetchone()
        if not row:raise ValueError('Run observation intelligence first')
        return json.loads(row['payload'])
def validated_cache(payload,text,classifier):
    tag=ObservationTag.model_validate(payload,context={'observation_text':text})
    if tag.taxonomy_version!=VERSION or tag.prompt_version!=PROMPT_VERSION:
        raise ValueError('Cache version mismatch')
    if not tag.fallback and tag.raw_status!='group_member_rules' and (tag.source!=classifier.name or tag.model!=classifier.model):
        raise ValueError('Cache provider mismatch')
    return tag

def classify_cached(text,classifier,connection):
    from backend.genai.classifier import cache_key
    from backend.analytics.intelligence_taxonomy import normalize
    text=normalize(text);key=cache_key(text,classifier.model,classifier.name)
    cached=connection.execute('SELECT payload FROM cache WHERE key=%s',(key,)).fetchone()
    if cached and os.getenv('AI_CACHE_ENABLED','true').lower()=='true':
        try:return validated_cache(json.loads(cached[0]),text,classifier)
        except ValueError:pass
    tag=classifier.classify(text)
    if os.getenv('AI_CACHE_ENABLED','true').lower()!='true':key+='-'+str(uuid.uuid4())
    text_hash=hashlib.sha256(text.encode()).hexdigest()
    connection.execute('INSERT INTO texts(hash,text) VALUES (%s,%s) ON CONFLICT(hash) DO NOTHING',(text_hash,text))
    connection.execute('INSERT INTO cache VALUES (%s,%s,%s) ON CONFLICT (key) DO UPDATE SET hash=EXCLUDED.hash,payload=EXCLUDED.payload',(key,text_hash,tag.model_dump_json()))
    return tag

def _run(provider='rules',model=None,dataset='all',batch_size=250,max_requests=None,enable_ai=None,taxonomy_version=VERSION,path=DB,embedding_model=None):
    from backend.genai.classifier import cache_key
    from backend.analytics.intelligence_taxonomy import rules
    if taxonomy_version!=VERSION:raise ValueError('Unsupported taxonomy version; supported: '+VERSION)
    if not 1<=batch_size<=2000:raise ValueError('Batch size must be 1â€“2000')
    started=time.monotonic();classifier=Classifier(provider,model,enable_ai,max_requests)
    runid=str(uuid.uuid4());cache_enabled=os.getenv('AI_CACHE_ENABLED','true').lower()=='true'
    grouping=Grouper(model_path=embedding_model)
    info={'id':runid,'status':'running','dataset':dataset,'provider':provider,'model':classifier.model,
          'taxonomy_version':VERSION,'prompt_version':PROMPT_VERSION,'created_at':datetime.now(timezone.utc).isoformat(),
          'cache_hits':0,'unique_processed':0,'api_requests':0,'classification_failures':0,
          'remote_enabled':classifier.gate.enabled,'redis_classification_hits':0,'representative_classifications':0,
          'group_member_rules':0,'embedding_model':grouping.embedding_model,'embedding_version':grouping.embedding_version}
    with db(path) as c:
        quality=c.execute("SELECT value FROM corpus WHERE key='quality'").fetchone()
        if not quality:raise ValueError('Import source corpus first')
        info['quality']=json.loads(quality[0]);c.execute('INSERT INTO runs VALUES (%s,%s)',(runid,json.dumps(info)))
        clause='' if dataset=='all' else ' WHERE dataset IN ('+','.join('%s' for _ in dataset.split(','))+')'
        params=[] if dataset=='all' else dataset.split(',')
        c.execute('INSERT INTO members SELECT %s,id FROM observations'+clause,[runid]+params)
        total=c.execute('SELECT count(*) FROM members WHERE run_id=%s',(runid,)).fetchone()[0]
        if not total:raise ValueError('No observations match dataset')
    last='';seen_groups=set();redis=get_cache()
    while True:
        with db(path) as c:
            batch=c.execute('SELECT t.hash,t.text FROM texts t WHERE t.hash>%s AND EXISTS (SELECT 1 FROM observations o JOIN members m ON m.observation_id=o.id WHERE o.hash=t.hash AND m.run_id=%s) ORDER BY t.hash LIMIT %s',(last,runid,batch_size)).fetchall()
        if not batch:break
        with db(path) as c:
            grouping.prepare(batch,c)
            for row in batch:
                h=row['hash'];text=row['text'];signals=rules(text)
                # Group before LLM classification using deterministic signals only.
                group,score,method=grouping.assign(h,text,signals['theme'])
                base=cache_key(text,classifier.model,provider);key=base
                tag=None;redis_key=redis.key('classification',[str(Path(path).resolve()),base])
                remote_cached=redis.get(redis_key) if cache_enabled else None
                if remote_cached is not None:
                    try:
                        tag=validated_cache(remote_cached,text,classifier)
                        info['redis_classification_hits']+=1
                    except ValueError:redis.bump('invalid')
                if tag is None and cache_enabled:
                    cached=c.execute('SELECT payload FROM cache WHERE key=%s',(base,)).fetchone()
                    if cached:
                        try:tag=validated_cache(json.loads(cached[0]),text,classifier)
                        except ValueError:pass
                if tag is not None:info['cache_hits']+=1
                elif group in seen_groups and provider not in ('rules','mock'):
                    # Never copy a representative's evidence, severity or rationale to a different text.
                    tag=ObservationTag(**signals,source='rules',model='deterministic',ai_generated=False,raw_status='group_member_rules')
                    info['group_member_rules']+=1
                else:
                    tag=classifier.classify(text);info['representative_classifications']+=1
                if not cache_enabled:key=base+'-'+runid
                c.execute('INSERT INTO cache VALUES (%s,%s,%s) ON CONFLICT (key) DO UPDATE SET hash=EXCLUDED.hash,payload=EXCLUDED.payload',(key,h,tag.model_dump_json()))
                if cache_enabled:redis.put(redis_key,tag.model_dump(),ttl=int(os.getenv('REDIS_CLASSIFICATION_TTL_SECONDS','86400')))
                c.execute('INSERT INTO assignments VALUES (%s,%s,%s,%s,%s,%s)',(runid,h,key,group,score,method))
                seen_groups.add(group);info['unique_processed']+=1;last=h
            info.update(api_requests=classifier.gate.requests,api_failures=classifier.gate.failures,
                        classification_failures=classifier.failures,embedding_cache_hits=grouping.cache_hits)
            c.execute('UPDATE runs SET payload=%s WHERE id=%s',(json.dumps(info),runid))
        print('Tagged unique texts',info['unique_processed'],'cache hits',info['cache_hits'],flush=True)
    with db(path) as c:
        stats=c.execute("SELECT count(*) total,count(DISTINCT o.hash) unique_texts,count(DISTINCT o.inspection_id) inspections,sum(((t.payload::jsonb ->> 'ai_generated')::boolean)::int) ai,sum((NOT (t.payload::jsonb ->> 'ai_generated')::boolean)::int) rules,sum(((t.payload::jsonb ->> 'fallback')::boolean)::int) fallbacks,sum(((t.payload::jsonb ->> 'theme')='Unclassified')::int) unclassified,avg((t.payload::jsonb ->> 'confidence')::double precision) confidence,sum(((t.payload::jsonb ->> 'severity')='High')::int) high_severity,sum(((t.payload::jsonb ->> 'severity')='Critical')::int) critical_severity,count(DISTINCT a.group_id) semantic_groups FROM observations o JOIN members m ON m.observation_id=o.id JOIN assignments a ON a.run_id=m.run_id AND a.hash=o.hash JOIN cache t ON t.key=a.cache_key WHERE m.run_id=%s",(runid,)).fetchone()
        info.update(dict(stats));info.update(status='completed',runtime_seconds=round(time.monotonic()-started,3),grouping_method=grouping.method,similarity_threshold=grouping.threshold,similarity_comparisons=grouping.comparisons)
        info['duplicate_text_occurrences']=info['total']-info['unique_texts'];info['ai_severity_index']=None
        info['ai_processed']=info['ai'];info['ai_fallback']=info['fallbacks'];info['api_calls']=info['api_requests']
        c.execute('UPDATE runs SET payload=%s WHERE id=%s',(json.dumps(info),runid))
    return info

def scope(run_id=None,path=DB,company=None,site=None,year=None,start_year=None,end_year=None,theme=None,severity=None,dataset=None,grain='inspection',product=None,inspection_type=None,observation_id=None,group_id=None,review_required=None):
    run_id=run_id or latest(path)['id'];where=['m.run_id=%s'];args=[run_id]
    for col,value in [('company',company),('site',site),('year',year),('dataset',dataset),('grain',grain),('product',product),('inspection_type',inspection_type),('id',observation_id)]:
        if value is not None and value!='':where.append('o.'+col+'=%s');args.append(value)
    for bound,op in [(start_year,'>='),(end_year,'<=')]:
        if bound is not None:where.append('o.year'+op+'%s');args.append(bound)
    if start_year and end_year and start_year>end_year:raise ValueError('Invalid year range')
    for key,value in [('theme',theme),('severity',severity)]:
        if value:where.append("(t.payload::jsonb ->> '"+key+"')=%s");args.append(value)
    if group_id:where.append('a.group_id=%s');args.append(group_id)
    if review_required is not None:
        where.append("coalesce(((t.payload::jsonb ->> 'reviewed')::boolean)::int,0)=%s");args.append(0 if review_required else 1)
    joined=' FROM observations o JOIN members m ON m.observation_id=o.id JOIN assignments a ON a.run_id=m.run_id AND a.hash=o.hash JOIN cache t ON t.key=a.cache_key WHERE '+' AND '.join(where)
    return run_id,joined,args

@snapshot_cache(TagsPage)
def tags(limit=25,offset=0,path=DB,**filters):
    if not 1<=limit<=200 or offset<0:raise ValueError('Invalid page')
    rid,joined,args=scope(path=path,**filters)
    with db(path) as c:
        total=c.execute('SELECT count(*)'+joined,args).fetchone()[0]
        ids=c.execute('SELECT o.id'+joined+' ORDER BY o.id LIMIT %s OFFSET %s',args+[limit,offset]).fetchall()
        data=[c.execute('SELECT o.*,(SELECT text FROM texts WHERE hash=o.hash) text,t.payload,a.group_id,a.similarity,a.method FROM observations o JOIN assignments a ON a.hash=o.hash JOIN cache t ON t.key=a.cache_key WHERE o.id=%s AND a.run_id=%s',(row[0],rid)).fetchone() for row in ids]
    with db(path) as c:
        runinfo=json.loads(c.execute('SELECT payload FROM runs WHERE id=%s',(rid,)).fetchone()[0])
        origins={r['id']:[json.loads(x[0]) for x in c.execute('SELECT origin FROM origins WHERE observation_id=%s',(r['id'],))] for r in data}
    result=[]
    for r in data:
        source=json.loads(r['source']);tag=ObservationTag.model_validate(json.loads(r['payload']),context={'observation_text':r['text']});tag.inspection_id=r['inspection_id'];tag.observation_id=r['id'];tag.dataset=r['dataset']
        result.append(ObservationRecord(observation_id=r['id'],inspection_id=r['inspection_id'],observation_hash=r['hash'],dataset=r['dataset'],grain=r['grain'],company=r['company'],site=r['site'],fiscal_year=r['year'],product=r['product'],inspection_type=r['inspection_type'],observation_text=r['text'],original_text=source['original_text'],source_observation_id=source.get('source_observation_id'),source_file=source['file'],source_sheet=source.get('sheet'),source_row=str(source.get('row')) if source.get('row') is not None else None,frequency=r['frequency'],tag=tag,observation_group_id=r['group_id'],similarity_score=float(r['similarity']),grouping_method=r['method'],embedding_model=runinfo.get('embedding_model'),embedding_version=runinfo.get('embedding_version'),origins=origins[r['id']]))
    return TagsPage(run_id=rid,total=total,records=result)

@snapshot_cache(MetricsPage)
def metrics(group_by='theme',path=DB,limit=200,**filters):
    if not 1<=limit<=1000:raise ValueError('Invalid group limit')
    if group_by not in ['theme','year','company','site','product','inspection_type']:raise ValueError('Invalid grouping')
    rid,joined,args=scope(path=path,**filters)
    dimension=None if group_by=='theme' else group_by
    selection='theme'+(','+dimension+' dimension' if dimension else '')
    group='theme'+(','+dimension if dimension else '')
    # Materialize only narrow analytical fields. Sorting full evidence payloads can
    # exceed available temporary disk space on a 285k-observation corpus.
    with db(path) as c:

        c.execute("CREATE TEMP TABLE cohort ON COMMIT DROP AS SELECT o.inspection_id,o.site,o.year,o.company,o.product,o.inspection_type,o.frequency,(t.payload::jsonb ->> 'theme') theme,(t.payload::jsonb ->> 'severity') severity,(t.payload::jsonb ->> 'ai_generated')::boolean ai_generated"+joined,args)
        total_groups=c.execute('SELECT count(*) FROM (SELECT '+group+' FROM cohort GROUP BY '+group+')').fetchone()[0]
        rows=c.execute('SELECT '+selection+",count(*) observation_count,count(DISTINCT inspection_id) inspection_count,count(DISTINCT site) unique_sites,sum(frequency) frequency_sum"+''.join(",sum((severity='"+s+"')::int) \""+s+"\"" for s in SEVERITY)+' FROM cohort GROUP BY '+group+' ORDER BY observation_count DESC,'+group+' LIMIT %s',(limit,)).fetchall()
        sev=c.execute("SELECT sum(CASE WHEN ai_generated AND severity!='Unclassified' THEN CASE severity WHEN 'Low' THEN 0.25 WHEN 'Medium' THEN 0.5 WHEN 'High' THEN 0.75 WHEN 'Critical' THEN 1.0 END END) points,sum((ai_generated AND severity!='Unclassified')::int) n FROM cohort").fetchone()
    result=[]
    for row in rows:
        r=dict(row);n=r['inspection_count'];dim=r.pop('dimension',None)
        result.append(ThemeMetric(theme=r['theme'],year=dim if group_by=='year' else None,company=dim if group_by=='company' else None,site=dim if group_by=='site' else None,product=dim if group_by=='product' else None,inspection_type=dim if group_by=='inspection_type' else None,observation_count=r['observation_count'],inspection_count=n,unique_sites=r['unique_sites'],recurrence_score=round(max(0,n-1)/n,6) if n else 0.,severity_distribution={s:r[s] for s in SEVERITY},frequency_sum=r['frequency_sum']))
    return MetricsPage(run_id=rid,grain=filters.get('grain','inspection') or 'all',groups=result,total_groups=total_groups,returned_limit=limit,ai_severity_index=sev['points']/sev['n'] if sev['n'] else None,ai_severity_observations=sev['n'] or 0)

@snapshot_cache(TagsPage)
def similar(observation_id,limit=20,path=DB,**filters):
    page=tags(observation_id=observation_id,limit=1,path=path,**filters)
    if not page.records:raise ValueError('Unknown observation')
    target=page.records[0]
    # Candidate groups were computed on unique texts; return cross-record evidence, not regulatory equivalence.
    with db(path) as c:
        candidates=c.execute('SELECT o.id FROM observations o JOIN members m ON m.observation_id=o.id JOIN assignments a ON a.run_id=m.run_id AND a.hash=o.hash WHERE m.run_id=%s AND a.group_id=%s AND o.id!=%s AND o.grain=%s ORDER BY o.id LIMIT %s',(page.run_id,target.observation_group_id,observation_id,target.grain,limit)).fetchall()
    return TagsPage(run_id=page.run_id,total=len(candidates),records=[tags(observation_id=r[0],run_id=page.run_id,grain=None,path=path,limit=1).records[0] for r in candidates])

def report(run_id=None,path=DB):
    run_id=run_id or latest(path)['id']
    with db(path) as c:
        row=c.execute('SELECT payload FROM runs WHERE id=%s',(run_id,)).fetchone()
        if not row:raise ValueError('Unknown run')
        info=json.loads(row[0])
    return {**info,'themes':metrics(run_id=run_id,path=path).model_dump(),'annual_themes':metrics(run_id=run_id,grain='annual_template',path=path).model_dump(),'notice':NOTICE}

def groups(limit=20,offset=0,path=DB,**filters):
    from backend.genai.contracts import GroupsPage,SemanticGroup
    if not 1<=limit<=200 or offset<0:raise ValueError('Invalid group page')
    rid,joined,args=scope(path=path,**filters)
    with db(path) as c:
        total=c.execute('SELECT count(DISTINCT a.group_id)'+joined,args).fetchone()[0]
        rows=c.execute('SELECT a.group_id,count(*) observation_count,count(DISTINCT o.hash) unique_texts,count(DISTINCT o.inspection_id) inspection_count,count(DISTINCT o.company) companies,count(DISTINCT o.site) sites,min(o.id) representative_id,min(a.method) grouping_method'+joined+' GROUP BY a.group_id ORDER BY observation_count DESC,a.group_id LIMIT %s OFFSET %s',args+[limit,offset]).fetchall()
    return GroupsPage(run_id=rid,total=total,groups=[SemanticGroup(**dict(r)) for r in rows])


def run(provider='rules',model=None,dataset='all',batch_size=250,max_requests=None,enable_ai=None,taxonomy_version=VERSION,path=DB,embedding_model=None):
    from backend.services.intelligence_lock import run_lock
    with run_lock(path):
        return _run(provider,model,dataset,batch_size,max_requests,enable_ai,taxonomy_version,path,embedding_model)
