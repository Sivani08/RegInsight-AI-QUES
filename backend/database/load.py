import argparse
import json
from pathlib import Path
import pandas as pd
from backend.database.store import Store

def load(directory='data/processed',store=None):
    path=Path(directory)
    if not (path/'quality.json').exists(): raise ValueError('Processed dataset missing. Run the ETL pipeline first.')
    q=json.loads((path/'quality.json').read_text(encoding='utf-8'))
    records=json.loads(pd.read_parquet(path/'inspections.parquet').to_json(orient='records',date_format='iso'))
    for r in records:
        if r.get('inspection_date'): r['inspection_date']=r['inspection_date'][:10]
        for key in ['inspection_year','inspection_month','inspection_recency','observation_count','citation_indicator','OAI_indicator','VAI_indicator','site_inspection_count','inspection_rank']:
            if r.get(key) is not None: r[key]=int(r[key])
    for name in ['rejected','duplicates']:
        q[name]=json.loads(pd.read_parquet(path/f'{name}.parquet').to_json(orient='records',date_format='iso'))
    if len(records)!=q['valid_records']: raise ValueError('Parquet count does not match quality report')
    return (store or Store()).replace(records,q)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--processed',default='data/processed'); a=p.parse_args()
    q=load(a.processed); print(f"Loaded {q['valid_records']} records; {q['data_label']}; dataset {q['dataset_id']}")
