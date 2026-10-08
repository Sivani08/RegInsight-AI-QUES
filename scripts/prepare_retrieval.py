"""Prepare derived analytical projections; migrations own persistent indexes."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database.store import Store
from backend.database.retrieval_mart import prepare
from backend.api.workspace import summary

def run():
    prepare(Store())
    for dataset in (None,'real'):
        summary(dataset=dataset)
    print('PostgreSQL retrieval projections ready.')

if __name__=='__main__':
    run()
