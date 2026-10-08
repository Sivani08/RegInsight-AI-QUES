"""Source-addressable PostgreSQL full-text lookup for reference documents."""
import json
from backend.database.postgres import connection


def sources():
    with connection('knowledge') as current:
        return [json.loads(row[0]) for row in current.execute('SELECT payload FROM sources ORDER BY id')]


def search(query, limit=10):
    if not query.strip():
        return []
    if not 1 <= limit <= 100:
        raise ValueError('Invalid reference result limit')
    with connection('knowledge') as current:
        rows = current.execute('''SELECT c.source_id, c.locator, c.text,
            s.payload::jsonb ->> 'title' AS title
            FROM chunks c JOIN sources s ON s.id=c.source_id
            WHERE c.search_vector @@ websearch_to_tsquery('english', %s)
            ORDER BY ts_rank_cd(c.search_vector, websearch_to_tsquery('english', %s)) DESC,
                     c.source_id, c.locator LIMIT %s''', (query, query, limit)).fetchall()
    return [{**row, 'authority': 'supplied reference; verify regulations separately'} for row in rows]
