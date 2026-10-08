"""Clearly labeled clinical operational demo; never mixed into real inspections."""
import csv,json
from pathlib import Path
from backend.services.qc_data import ImportRequest,QCRecord,ingest,ROOT
from backend.services.qc_signals import month_label,month_number

def generate():
    rows=[]
    for study_index,study in enumerate(['ONCO-301','CARD-112','NEURO-045']):
        for site in range(1,4):
            for month in range(12):
                for metric_index,metric in enumerate(['etmf_missing','aged_queries','deviations']):
                    value=3+site+study_index+metric_index+(month*2 if study_index==0 else month//3)
                    rows.append({'study':study,'site':f'{study}-SITE-{site:02}','month':month_label(month_number('2025-09')+month),'metric':metric,'numerator':value,'denominator':100})
    folder=ROOT/'data/qc/demo';folder.mkdir(parents=True,exist_ok=True)
    path=folder/'clinical_quality_metrics.csv'
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=list(QCRecord.model_fields));writer.writeheader();writer.writerows(rows)
    return ingest(ImportRequest(name='ClinQC synthetic operational demonstration',kind='demo',records=[QCRecord(**r) for r in rows]),source=str(path.relative_to(ROOT)))
if __name__=='__main__':print(json.dumps(generate(),indent=2))
