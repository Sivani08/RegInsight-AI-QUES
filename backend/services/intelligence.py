from collections import defaultdict
from backend.services.mart import read_entities,names
from backend.analytics.metrics import analyze_trend, find_recurring_risks
from backend.risk.engine import calculate_risk,load_config

class Intelligence:
    def __init__(self,store):
        self.store=store
        self.config=load_config()

    def info(self):
        info=self.store.info()
        if not info: raise ValueError('No dataset loaded. Run the ETL pipeline, then backend.database.load.')
        return info

    def risk(self,**filters):
        return calculate_risk(self.store.search(lightweight=True,**filters),self.info()['as_of'],self.config)

    def trend(self,theme=None,start_year=None,end_year=None,**filters):
        if start_year and end_year and start_year>end_year: raise ValueError('Start year must not exceed end year')
        info=self.info()
        if info.get('dashboard_cache') and not theme and not any(filters.values()):
            if info['dashboard_cache']['methodology']!=self.config:raise ValueError('Risk configuration changed. Rebuild the materialized summaries before serving this dataset.')
            return [r for r in info['dashboard_cache']['trend'] if (not start_year or r['year']>=start_year) and (not end_year or r['year']<=end_year)]
        return analyze_trend(self.store.search(lightweight=True,**filters),self.info()['as_of'],self.config,theme,start_year,end_year)

    def recurrence(self,group_by=None,**filters):
        return find_recurring_risks(self.store.search(lightweight='recurrence',**filters),group_by)

    def company_names(self):
        if self.info().get('mart_ready'):return names(self.store)
        return sorted({r['company_name'] for r in self.store.search() if r.get('company_name')})

    def entities(self,kind='site',search=None,limit=200,**filters):
        if self.info().get('mart_ready') and not any(v for k,v in filters.items() if k!='company'):
            return read_entities(self.store,kind,filters.get('company'),search,limit)
        grouped=defaultdict(list)
        for r in self.store.search(lightweight=True,**filters):
            key=r.get('company_key') if kind=='company' else r.get('site_key')
            grouped[key or 'unknown'].append(r)
        result=[]
        as_of=self.info()['as_of']
        for key,records in grouped.items():
            first=records[0]
            result.append({'key':key,'company_name':first.get('company_name') or 'Unknown company',
                'site_name':first.get('site_name') if kind=='site' else None,
                'fei_number':first.get('fei_number') if kind=='site' else None,
                'country':', '.join(sorted({r['country'] for r in records if r.get('country')})),
                'risk':calculate_risk(records,as_of,self.config)})
        if search:result=[r for r in result if search.lower() in r['company_name'].lower()]
        return sorted(result,key=lambda r: (-(r['risk']['score'] if r['risk']['score'] is not None else -1),r['key']))[:limit]

    def profile(self,**filters):
        records=self.store.search(**filters)
        if not records: raise ValueError('No inspections match this company or site.')
        return {'risk':self.risk(**filters),'trend':self.trend(**filters),'recurrence':self.recurrence(**filters),
                'records':records,'info':{k:self.info()[k] for k in ['as_of','data_label','dataset_id']}}

    def dashboard(self,**filters):
        from backend.analytics.dashboard_queries import dashboard
        return dashboard(self,filters)
