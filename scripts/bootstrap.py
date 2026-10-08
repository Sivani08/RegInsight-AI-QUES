"""Explicit operator startup; never replaces an existing loaded database by default."""
import argparse
import os
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
os.chdir(ROOT)
from backend.database.store import Store
from backend.database.load import load
from data_engineering.sample import generate
from data_engineering.pipeline import run

def main():
    p=argparse.ArgumentParser();p.add_argument('--serve',action='store_true');p.add_argument('--as-of',default='2026-09-10');p.add_argument('--host',default='0.0.0.0');p.add_argument('--port',type=int,default=8000)
    a=p.parse_args();store=Store()
    if store.info() is None:
        if not (ROOT/'data/processed/quality.json').exists():
            source=ROOT/'data/sample/synthetic_inspections.csv'
            if not source.exists(): generate(source)
            run(source,ROOT/'config/schema_mapping.yaml',ROOT/'data/processed',a.as_of,synthetic=True)
        q=load(ROOT/'data/processed',store)
        print(f"Loaded {q['valid_records']} records — {q['data_label']}")
    else: print('Existing dataset retained.')
    if a.serve:
        import uvicorn
        uvicorn.run('backend.api.main:app',host=a.host,port=a.port)
if __name__=='__main__':main()
