"""A rebuildable, narrow browsing index over immutable observation snapshots."""
import threading
import json
from data_engineering.intelligence_sources import db

_lock = threading.Lock()
_ready = set()


def ensure(path, run_id):
    key = (str(path), run_id)
    if key in _ready:
        return
    with _lock:
        if key in _ready:
            return
        with db(path) as c:
            # Allow initial snapshot indexing to finish on slower disks. Later
            # calls reuse the completed index.
            c.execute("SET LOCAL statement_timeout = '15min'")
            run = c.execute('SELECT payload FROM runs WHERE id=%s',(run_id,)).fetchone()
            if not run or json.loads(run[0]).get('status') != 'completed':
                raise ValueError('A completed observation snapshot is required')
            c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ('website-index:' + run_id,))
            if not c.execute('SELECT 1 FROM website_index_runs WHERE run_id=%s',(run_id,)).fetchone():
                # The bounded classification set is the outer relation. Large original
                # source JSON never enters the browsing index or a sorting temporary table.
                c.execute('''INSERT INTO website_index
                    SELECT a.run_id,o.id,o.hash,o.inspection_id,o.dataset,o.grain,o.company,o.site,o.year,
                        a.group_id,(t.payload::jsonb ->> 'theme'),(t.payload::jsonb ->> 'severity'),
                        CASE (t.payload::jsonb ->> 'severity') WHEN 'Critical' THEN 4
                        WHEN 'High' THEN 3 WHEN 'Medium' THEN 2 WHEN 'Low' THEN 1 ELSE 0 END
                    FROM assignments a JOIN cache t ON t.key=a.cache_key
                    JOIN observations o ON o.hash=a.hash
                    JOIN members m ON m.run_id=a.run_id AND m.observation_id=o.id
                    WHERE a.run_id=%s ON CONFLICT DO NOTHING''',(run_id,))
                c.execute('INSERT INTO website_index_runs VALUES (%s)',(run_id,))
                c.execute('ANALYZE website_index')
        _ready.add(key)
