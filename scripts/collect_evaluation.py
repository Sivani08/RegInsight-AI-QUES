"""Collect live answers; independently derive expected facts from canonical SQL.

No application query helpers are used to construct the expected answers.
"""
import json,time,urllib.request,argparse,getpass,http.cookiejar
from pathlib import Path
from backend.database.postgres import connection
ROOT=Path(__file__).resolve().parents[1]

def run():
    parser=argparse.ArgumentParser();parser.add_argument('--base-url',default='http://127.0.0.1:8018')
    parser.add_argument('--output',default=str(ROOT/'evaluation/cases.json'))
    args=parser.parse_args();opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()));cases=[]
    key=getpass.getpass('Individual access key: ')
    request=urllib.request.Request(args.base_url+'/api/auth/login',data=json.dumps({'access_key':key}).encode(),headers={'Content-Type':'application/json'})
    with opener.open(request,timeout=30) as response:
        response.read()
    del key
    with connection() as c:
        dataset=json.loads(c.execute('SELECT payload FROM dataset WHERE id=1').fetchone()[0])['dataset_id']
        for name,filters,offset in [('portfolio',{},0),('year-2025',{'year':2025},0),
            ('oai',{'classification':'OAI'},0),('year-and-classification',{'year':2020,'classification':'OAI'},0),
            ('empty',{'company':'__EVALUATION_NO_MATCH__'},0),('second-page',{'year':2025},5)]:
            clauses=[];params=[]
            for k,v in filters.items():
                clauses.append({'year':'inspection_year','classification':'classification','company':'company_key'}[k]+'=%s')
                params.append(v.casefold() if k=='company' else v)
            where=' WHERE '+' AND '.join(clauses) if clauses else ''
            n=c.execute('SELECT count(*) FROM inspections'+where,params).fetchone()[0]
            counts={row[0]:row[1] for row in c.execute('SELECT classification,count(*) FROM inspections'+where+' GROUP BY classification',params)}
            sources=[]
            for row in c.execute('SELECT inspection_id,payload FROM inspections'+where+' ORDER BY inspection_year DESC,inspection_id LIMIT 5 OFFSET %s',params+[offset]):
                iid,payload=row[0],row[1]
                r=json.loads(payload);sources.append(dict(inspection_id=iid,quote=(r.get('observation_text') or '')[:1200],company=r.get('company_name'),site=r.get('site_name'),classification=r.get('classification'),inspection_date=r.get('inspection_date')))
            body=dict(question='Show the inspections.',focus='inspection_activity',filters=filters,limit=5,offset=offset)
            for phase,budget in [('first',5000),('repeat',1000)]:
                start=time.perf_counter()
                with opener.open(urllib.request.Request(args.base_url+'/api/agent/dashboard-query',data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=120) as response:
                    output=json.load(response)
                elapsed=(time.perf_counter()-start)*1000
                actual=dict(metrics=output['layers']['metrics'],records=output['layers']['evidence_and_limitations']['records'],
                    filters={k:v for k,v in output['semantic_plan']['filters'].items() if v is not None},offset=output['offset'],elapsed_ms=elapsed)
                expected=dict(metrics={'total_inspections':n,**{k:counts.get(k,0) for k in ('NAI','VAI','OAI')}},
                    ids=[r['inspection_id'] for r in sources],filters=filters,offset=offset,budget_ms=budget)
                cases.append(dict(name=name+'-'+phase,input=json.dumps(body),actual_output=json.dumps(actual),expected_output=json.dumps(expected),retrieval_context=[json.dumps(r) for r in sources]))
                print(name,phase,round(elapsed,2),'ms',flush=True)
    Path(args.output).write_text(json.dumps({'dataset_id':dataset,'cases':cases},indent=2),encoding='utf-8')
if __name__=='__main__':run()
