import re
import uuid
from datetime import datetime,timezone
from backend.tools.registry import Tools
from backend.analytics.taxonomy import THEMES

def display_rate(value): return 'unavailable' if value is None else f'{value*100:.1f}%'

class InspectionAgent:
    def __init__(self,service): self.service=service

    def query(self,question,company=None,site=None,observation_text=None):
        if not question.strip(): raise ValueError('Enter an investigation question.')
        q=question.lower()
        observation_intent=('observations' in q and any(w in q for w in ['high','critical','repeated','recurring','similar','evidence'])) or ('regulatory themes' in q) or ('themes increased between fy' in q) or ('classified as' in q) or ('evidence for' in q and 'classification' in q) or ('recurring issues at this site' in q)
        observation_intent=observation_intent or any(w in q for w in ['semantic group','severity distribution','human review','recurrence by']) or ('observation' in q and any(w in q for w in ['theme','evidence','classified','explain'])) or ('compare' in q and 'themes' in q) or ('evidence' in q and 'classification' in q)
        if observation_intent:
            from backend.agents.observation_investigator import investigate
            return investigate(self.service,question,company,site)
        tools=Tools(self.service); info=self.service.info(); q=question.lower()
        names=set(self.service.company_names())
        stopwords=set('the a an why is this company companies site sites high low risk which show compare for of and what are over last years food management first selected considered recurring deficiencies themes increased highest regulatory how has since'.split())
        contextual=bool(company or site) and any(x in q for x in ['this company','this site','selected'])
        matched=[] if contextual else sorted([name for name in names if name.strip() and
            name.lower() not in stopwords and len(name)>3 and
            re.search(r'(?<!\w)'+re.escape(name.lower())+r'(?!\w)',q)])
        matched=[name for name in matched if not any(name.lower() in other.lower() and len(other)>len(name) for other in matched)]
        if not matched and not contextual:
            matched=sorted([name for name in names if name.split() and len(name.split()[0])>=4 and
                name.split()[0].lower() not in stopwords and re.search(r'\b'+re.escape(name.split()[0].lower())+r'\b',q)])
        explicit_names=bool(matched)
        if explicit_names: site=None
        if company and not matched and any(x in q for x in ['this company','this site','selected','theme','recurring']):
            resolved=next((n for n in names if n.lower()==company.lower()),None)
            if not resolved: raise ValueError('Unknown company. Choose a company from the loaded dataset.')
            matched=[resolved]
        if len(matched)>2: raise ValueError('Company name is ambiguous. Select an exact legal name from company search, or name exactly two companies to compare.')
        if 'compare' in q and len(matched)!=2: raise ValueError('Name two companies from the loaded dataset to compare.')
        explicit_sites=[s for s in self.service.entities() if (s.get('site_name') and s['site_name'].lower() in q) or (s.get('fei_number') and s['fei_number'].lower() in q)]
        if not site and len(explicit_sites)==1: site=explicit_sites[0]['key']
        if len(explicit_sites)>1: raise ValueError('Select one site, or compare two companies.')
        years=[int(x) for x in re.findall(r'\b(?:19|20)\d{2}\b',q)]
        bounds={}
        if years:
            bounds={'start_year':min(years)}
            if len(years)>1: bounds['end_year']=max(years)
        mode='comparison' if len(matched)==2 else 'investigation'
        filters=[{'company':n,**bounds} for n in matched]
        if site:
            if not self.service.store.search(site=site): raise ValueError('Unknown site or FEI. Choose a site in the dataset.')
            filters=[{'site':site,**bounds}]
        if not filters:
            if any(x in q for x in ['companies','sites','management','highest','portfolio','oai','vai','nai','themes','data-integrity','data integrity']):
                if any(x in q for x in ['highest','management','investigate first','companies']):
                    mode='ranking'
                    kind='company' if 'companies' in q else 'site'
                    entities=self.service.entities(kind,**bounds)[:5]
                    filters=[{('company' if kind=='company' else 'site'):(e['company_name'] if kind=='company' else e['key']),**bounds} for e in entities]
                else: filters=[bounds]; mode='portfolio'
            elif observation_text: filters=[]
            else: raise ValueError('Could not identify a company or site. Select one, or ask about the portfolio, highest-risk sites, themes or OAI trends.')
        results=[]; evidence_records={}
        for scope in filters:
            if self.service.info()['valid_records']>10000 and not any(scope.get(k) for k in ['company','site','fei_number']):
                raise ValueError('For this large dataset, select a company or site for record-level agent evidence. Use Dashboard, Trends and Annual Benchmarks for portfolio-wide analysis.')
            records=tools.call('search_inspections',**scope)
            if not records: raise ValueError('No inspection records match the investigation scope.')
            risk=tools.call('calculate_risk',**scope)
            trend=tools.call('analyze_trend',**scope)
            recurrence=tools.call('find_recurring_risks',**scope)
            for r in records: evidence_records[r['inspection_id']]=r
            # One combined, bounded text interpretation per investigated entity. No metrics reach the provider.
            excerpts=[r for r in records if r.get('observation_text')][:3]
            interpretation=None
            if excerpts:
                interpretation=tools.call('analyze_observation',observation_text='\n'.join(r['observation_text'] for r in excerpts)[:20000])
                interpretation['inspection_ids']=[r['inspection_id'] for r in excerpts]
            name=scope.get('company') or (records[0].get('site_name') if scope.get('site') else 'Portfolio')
            drivers=sorted([c for c in risk['components'] if c['points'] is not None],key=lambda c:-c['points'])[:3]
            score_text='unavailable' if risk['score'] is None else f"{risk['score']:.2f}/100"
            explanation=f"{name}: {risk['band']} risk, score {score_text}, based on {len(records)} inspections. Citation rate is {display_rate(risk['metrics']['citation_rate'])} across {risk['metrics']['citation_known']} known flags; {risk['metrics']['OAI']} OAI inspections across {risk['metrics']['classification_known']} known classifications."
            change=round(trend[-1]['risk_score']-trend[0]['risk_score'],2) if len(trend)>=2 and trend[-1]['risk_score'] is not None and trend[0]['risk_score'] is not None else None
            results.append({'entity':name,'scope':scope,'answer':explanation,'risk':risk,'why':drivers,'trend':trend,
                'risk_change_points':change,'recurring_issues':recurrence,'observation_interpretation':interpretation})
        theme_changes=[]
        if any(x in q for x in ['theme','data integrity','data-integrity']) and any(x in q for x in ['increas','changed','last three','last 3']):
            scope=filters[0] if len(filters)==1 else bounds
            records=tools.call('search_inspections',**scope)
            available_years=sorted({r['inspection_year'] for r in records if r.get('inspection_year')})
            if len(available_years)>=2:
                first=available_years[-1]-2 if 'last three' in q or 'last 3' in q else available_years[0]
                last=available_years[-1]
                recurring=tools.call('find_recurring_risks',group_by='inspection_year',**scope)
                for theme in THEMES:
                    by_year={int(r['group']):r['count'] for r in recurring if r['theme']==theme and r['group']!='Unknown'}
                    baseline=by_year.get(first,0) if any(r.get('inspection_year')==first and r.get('observation_text') for r in records) else None
                    latest=by_year.get(last,0) if any(r.get('inspection_year')==last and r.get('observation_text') for r in records) else None
                    theme_changes.append({'theme':theme,'start_year':first,'end_year':last,'start_count':baseline,'end_count':latest,'change':latest-baseline if latest is not None and baseline is not None else None})
                if 'data integrity' in q or 'data-integrity' in q:
                    theme_changes=[r for r in theme_changes if r['theme']=='Data Integrity']
                theme_changes.sort(key=lambda r:(r['change'] is None,-(r['change'] or 0),r['theme']))
        standalone=tools.call('analyze_observation',observation_text=observation_text) if observation_text else None
        analysis_id=str(uuid.uuid4())
        payload={'analysis_id':analysis_id,'question':question,'mode':mode,'created_at':datetime.now(timezone.utc).isoformat(),
            'dataset_id':info['dataset_id'],'data_label':info['data_label'],'as_of':info['as_of'],
            'methodology':self.service.config,'results':results,'theme_changes':theme_changes,
            'standalone_observation':standalone,'tools':tools.trace,'records':list(evidence_records.values()),
            'limitations':['Rule-based intent routing; unsupported or ambiguous entities require clarification.',
                          'All numeric claims come from tools. Observation interpretation never changes a score.',
                          'Year counts may compare partial periods. Theme counts are keyword signals, not confirmed violations.']}
        self.service.store.save_evidence(analysis_id,payload)
        verified=tools.call('get_evidence',analysis_id=analysis_id)
        self.service.store.update_evidence_trace(analysis_id,tools.trace)
        return {**{k:v for k,v in verified.items() if k!='records'},'tools':tools.trace,'evidence_count':len(evidence_records)}
