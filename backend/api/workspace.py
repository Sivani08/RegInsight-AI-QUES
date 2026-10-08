"""Read-only corpus browsing and append-only human review for the website."""
import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, HTTPException, Query, Request
from backend.api.identity import reviewer
from pydantic import BaseModel, Field, field_validator
from backend.services import observation_intelligence as intelligence
from data_engineering.intelligence_sources import db, DB
from backend.cache.retrieval import workspace_cache

router = APIRouter(prefix='/api/workspace')


def review_table(c):
    # Migrations own table creation; the existing call sites remain compatible.
    return None


def cohort(run_id=None, dataset=None, severity=None, year=None, theme=None, search=None):
    from backend.services.website_index import ensure
    rid = run_id or intelligence.latest(DB)['id']
    ensure(DB, rid)
    joined = " FROM website_index o WHERE o.run_id=%s AND o.grain='inspection'"
    args = [rid]
    for column, value in [('dataset',dataset),('severity',severity),('year',year),('theme',theme)]:
        if value is not None and value != '':
            joined += ' AND o.' + column + '=%s'
            args.append(value)
    if search:
        # Literal substring matching: LIKE wildcards are never interpreted.
        from backend.services.retrieval_search import text_predicate,candidate_predicate
        with db(DB) as c:
            subquery,text_args=text_predicate(c,search)
            candidates,candidate_args=candidate_predicate(c,search,rid)
        joined+=candidates;args+=candidate_args
        joined += ''' AND (strpos(lower(coalesce(o.company,'')),lower(%s))>0
            OR strpos(lower(coalesce(o.site,'')),lower(%s))>0
            OR strpos(lower(coalesce(o.inspection_id,'')),lower(%s))>0
            OR o.hash IN (''' + subquery + '))'
        args += [search] * 3 + text_args
    return rid, joined, args


@router.get('/summary')
@workspace_cache
def summary(dataset: str | None = None, run_id: str | None = None):
    run = intelligence.latest(DB)
    if run_id and run_id!=run['id']:
        with db(DB) as c:
            row=c.execute('SELECT payload FROM runs WHERE id=%s',(run_id,)).fetchone()
        if not row:raise ValueError('Observation run not found')
        run=json.loads(row[0])
    rid, joined, args = cohort(run_id=run['id'], dataset=dataset)
    with db(DB) as c:
        stored=c.execute('SELECT payload FROM retrieval_summaries WHERE run_id=%s AND dataset=%s',(rid,dataset or '')).fetchone()
        if stored:return json.loads(stored[0])

        c.execute('''CREATE TEMP TABLE website_cohort ON COMMIT DROP AS SELECT o.inspection_id,
            o.year, o.site, o.dataset, o.group_id, o.theme, o.severity''' + joined, args)
        stats = dict(c.execute('''SELECT count(*) observations,
            count(DISTINCT inspection_id) inspections,
            count(DISTINCT site) sites,
            coalesce(sum((severity IN ('High','Critical'))::int),0) high_severity
            FROM website_cohort''').fetchone())
        themes = [dict(r) for r in c.execute('''SELECT theme, count(*) count,
            count(DISTINCT inspection_id) inspections FROM website_cohort
            GROUP BY theme ORDER BY count DESC, theme''')]
        trend = [dict(r) for r in c.execute('''SELECT year, count(*) observations,
            count(DISTINCT inspection_id) inspections FROM website_cohort
            WHERE year IS NOT NULL GROUP BY year ORDER BY year''')]
        severity = [dict(r) for r in c.execute('''SELECT severity label,count(*) count
            FROM website_cohort GROUP BY severity ORDER BY count DESC''')]
        datasets = [dict(r) for r in c.execute('''SELECT dataset,count(*) count
            FROM website_cohort GROUP BY dataset ORDER BY dataset''')]
        stats['recurring_themes'] = sum(r['inspections'] > 1 and r['theme'] != 'Unclassified' for r in themes)
    result=dict(run_id=rid, created_at=run['created_at'], provider=run['provider'],
        model=run['model'], stats=stats, themes=themes, trend=trend,
        severity=severity, datasets=datasets, grain='inspection')
    with db(DB) as c:
        c.execute('INSERT INTO retrieval_summaries VALUES (%s,%s,%s) ON CONFLICT (run_id,dataset) DO UPDATE SET payload=EXCLUDED.payload',(rid,dataset or '',json.dumps(result)))
    return result


@router.get('/observations')
@workspace_cache
def observations(run_id: str | None = None, dataset: str | None = None,
        severity: str | None = None, year: int | None = None,
        theme: str | None = None, search: str | None = Query(None, max_length=200),
        sort: Literal['date','facility','theme','severity','inspection'] = 'date',
        direction: Literal['asc','desc'] = 'desc',
        limit: int = Query(8, ge=1, le=50), offset: int = Query(0, ge=0)):
    rid, joined, args = cohort(run_id, dataset, severity, year, theme, search)
    column = {'date':'o.year','facility':'o.company','theme':'o.theme',
        'severity':'o.severity_rank',
        'inspection':'o.inspection_id'}[sort]
    with db(DB) as c:

        total = c.execute('SELECT count(*)' + joined, args).fetchone()[0]
        ids = c.execute('SELECT o.id' + joined + ' ORDER BY ' + column + ' ' + direction + ',o.id LIMIT %s OFFSET %s', args + [limit, offset]).fetchall()
    records = []
    with db(DB) as c:
        review_table(c)
        for row in ids:
            record = intelligence.tags(run_id=rid, observation_id=row[0], path=DB, limit=1).records[0].model_dump()
            # Start from the indexed group, rather than rescanning the full corpus per row.
            recurrence = c.execute('''SELECT count(DISTINCT o.inspection_id) FROM website_index o
                WHERE o.run_id=%s AND o.group_id=%s AND o.grain='inspection' AND o.dataset=%s''',
                (rid, record['observation_group_id'], record['dataset'])).fetchone()[0]
            reviewed = c.execute('''SELECT payload FROM website_reviews WHERE run_id=%s
                AND observation_id=%s ORDER BY revision DESC LIMIT 1''', (rid, row[0])).fetchone()
            record.update(related_inspections=recurrence, review=json.loads(reviewed[0]) if reviewed else None)
            records.append(record)
    return dict(run_id=rid, total=total, records=records, offset=offset, limit=limit)


class Review(BaseModel):
    run_id: str = Field(min_length=1, max_length=100)
    observation_id: str = Field(min_length=1, max_length=512)
    revision: int = Field(ge=0)
    action: Literal['Approve','Modify','Reject']
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=1, max_length=2000)
    theme: str | None = Field(None, max_length=150)
    severity: Literal['Low','Medium','High','Critical','Unclassified'] | None = None

    @field_validator('reviewer','note')
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError('A nonblank value is required')
        return value.strip()


@router.get('/reviews')
def history(run_id: str, observation_id: str):
    with db(DB) as c:
        review_table(c)
        return [json.loads(r[0]) for r in c.execute('''SELECT payload FROM website_reviews
            WHERE run_id=%s AND observation_id=%s ORDER BY revision DESC''', (run_id, observation_id))]


@router.post('/reviews', status_code=201)
def review(body: Review, request: Request):
    actor=reviewer(request)
    from backend.analytics.intelligence_taxonomy import THEME_NAMES
    page = intelligence.tags(run_id=body.run_id, observation_id=body.observation_id, limit=1, path=DB)
    if not page.records:
        raise HTTPException(404, 'Observation not found in this snapshot')
    if body.action == 'Modify' and (body.theme not in THEME_NAMES or body.severity is None):
        raise HTTPException(422, 'Choose a supported theme and severity for a modification')
    with db(DB) as c:
        review_table(c)
        c.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", ('reginsight-review',))
        current = c.execute('''SELECT coalesce(max(revision),0) FROM website_reviews
            WHERE run_id=%s AND observation_id=%s''', (body.run_id, body.observation_id)).fetchone()[0]
        if body.revision != current:
            raise HTTPException(409, 'Another review was saved. Refresh the history and review the latest decision.')
        payload = {**body.model_dump(), 'revision': current + 1, 'reviewer':actor.name,'reviewer_id':actor.user_id,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'identity': 'Authenticated account; decision support review',
            'original_classification': page.records[0].tag.model_dump()}
        c.execute('INSERT INTO website_reviews VALUES (%s,%s,%s,%s)',
            (body.run_id, body.observation_id, current + 1, json.dumps(payload)))
    return payload
