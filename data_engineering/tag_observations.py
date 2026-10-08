"""Tag every compatible source snapshot; the original demo remains --dataset demo-legacy."""
import argparse,json,os,gzip
from pathlib import Path
from backend.analytics.intelligence_taxonomy import VERSION
from data_engineering.intelligence_sources import DB,ROOT,db,ingest
from backend.services.observation_intelligence import run,report
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--dataset',default='all');p.add_argument('--provider',default=os.getenv('AI_PROVIDER','rules'));p.add_argument('--model');p.add_argument('--batch-size',type=int,default=int(os.getenv('AI_BATCH_SIZE','250')));p.add_argument('--max-requests',type=int,default=int(os.getenv('AI_MAX_REQUESTS') or os.getenv('AI_MAX_REQUESTS_PER_RUN','20')));p.add_argument('--enable-ai',action='store_true',default=None);p.add_argument('--output',default='data/intelligence/latest');p.add_argument('--taxonomy-version',default=VERSION);p.add_argument('--database',default=str(DB));p.add_argument('--embedding-model');p.add_argument('--inventory',action='store_true');a=p.parse_args()
    try:
        if a.dataset=='demo-legacy':
            from backend.services.observations import run_batch,export
            result=run_batch(a.provider,a.model,enable_ai=a.enable_ai);export(result['id'],a.output)
        else:
            if a.inventory:
                from data_engineering.dataset_inventory import inventory
                inventory()
            with db(a.database) as c:loaded=c.execute('SELECT 1 FROM corpus LIMIT 1').fetchone()
            if not loaded:ingest(path=a.database)
            info=run(provider=a.provider,model=a.model,dataset=a.dataset,batch_size=a.batch_size,max_requests=a.max_requests,enable_ai=a.enable_ai,taxonomy_version=a.taxonomy_version,path=a.database,embedding_model=a.embedding_model)
            result=report(info['id'],path=a.database)
            out=Path(a.output);out.mkdir(parents=True,exist_ok=True);(out/'report.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
            with db(a.database) as c,gzip.open(out/'tags.jsonl.gz','wt',encoding='utf-8') as f:
                for row in c.execute('SELECT o.id observation_id,o.inspection_id,o.hash observation_hash,o.dataset,o.company,o.site,o.year fiscal_year,o.product,o.inspection_type,o.source,(SELECT text FROM texts WHERE hash=o.hash) normalized_observation,a.group_id,a.similarity similarity_score,a.method grouping_method,t.payload FROM observations o JOIN members m ON m.observation_id=o.id JOIN assignments a ON a.run_id=m.run_id AND a.hash=o.hash JOIN cache t ON t.key=a.cache_key WHERE m.run_id=%s ORDER BY o.id',(info['id'],)):
                    value=dict(row);value['source']=json.loads(value['source']);value['tag']=json.loads(value.pop('payload'));value['tag'].update(observation_id=value['observation_id'],inspection_id=value['inspection_id'],dataset=value['dataset']);value.update(embedding_model=info['embedding_model'],embedding_version=info['embedding_version']);f.write(json.dumps(value,ensure_ascii=False)+'\n')
        print(json.dumps({k:v for k,v in result.items() if k not in ['themes','annual_themes']},indent=2))
    except ValueError as e:p.exit(2,str(e)+'\n')
