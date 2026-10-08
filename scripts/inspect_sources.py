import json
from sqlalchemy import select
from backend.database.store import Store,inspections
s=Store();
with s.engine.connect() as c:
 r=c.execute(select(inspections.c.payload).limit(1)).scalar_one()
 print({k:str(v)[:160] for k,v in r.items() if 'source' in k})
 print('files',[(str(p),p.stat().st_size) for p in __import__('pathlib').Path('data').rglob('*.db')])
