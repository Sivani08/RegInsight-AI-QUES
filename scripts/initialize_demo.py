"""Explicit synthetic initialization; never overwrites a loaded inspection corpus."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.database.store import Store,ROOT
from backend.database.load import load
from data_engineering.intelligence_sources import db,ingest
from backend.services.observation_intelligence import run

def main():
    store=Store()
    if store.info() is None:
        if not (ROOT/'data/processed/inspections.parquet').exists():
            raise SystemExit('Regenerate the bundled synthetic fixture with data_engineering.pipeline first.')
        load(ROOT/'data/processed',store)
    with db() as current:
        loaded=current.execute('SELECT 1 FROM corpus LIMIT 1').fetchone()
        classified=current.execute("SELECT 1 FROM runs WHERE payload::jsonb->>'status'='completed' LIMIT 1").fetchone()
    if not loaded:
        ingest()
    if not classified:
        run()
    from backend.services.mart import build
    if not store.info().get('mart_ready'):
        build(store)
    print('Existing data retained; synthetic demonstration is ready.')

if __name__=='__main__':
    main()
