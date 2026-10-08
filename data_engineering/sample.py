"""Reproducible, explicitly synthetic inspection-level records; no real companies."""
import csv
import random
from pathlib import Path

THEMES = [
    'Audit trail disabled; data integrity controls failed and records were deleted.',
    'OOS investigation lacked a documented root cause and follow-up testing.',
    'CAPA effectiveness was not verified after repeated deviations.',
    'Documentation was incomplete; batch records lacked review signatures.',
    'Laboratory controls did not include instrument calibration verification.',
    'Process validation did not establish reproducible manufacturing controls.',
]

def generate(path: Path):
    rng = random.Random(483)
    columns = ['Inspection ID','FEI','Company','Site','Inspection Date','Country','Product',
               'Inspection Type','Classification','Citation','Observations','Project Area',
               'Observation Text','Fiscal Year']
    rows = []
    companies = ['Aster Therapeutics','Northstar Biologics','Meridian Laboratories',
                 'Cedar Health Sciences','Helix Formulations','Summit Medical']
    for c, company in enumerate(companies):
        for s in range(2):
            for year in range(2020,2027):
                for visit in range(2 + ((c+s+year) % 2)):
                    # Deteriorating Aster; improving Northstar; stable low Cedar.
                    probability = (0.20 + (year-2020)*0.13 if c == 0 else
                                   0.9 - (year-2020)*0.13 if c == 1 else
                                   0.06 if c == 3 else 0.45 + s*0.15)
                    adverse = rng.random() < probability
                    classification = ('OAI' if rng.random() < probability else 'VAI') if adverse else 'NAI'
                    count = rng.randint(2,7) if adverse else 0
                    text = ' '.join(THEMES[:3] if c == 0 and adverse else rng.sample(THEMES,2)) if adverse else ''
                    month = 1 + visit*3
                    rows.append([f'SYN-{len(rows)+1:05}',f'SYN-FEI-{c+1:03}{s+1}',company,
                                 f'{company.split()[0]} Site {s+1}',f'{year}-{month:02}-15',
                                 ['India','United States','Ireland'][c%3],
                                 ['Drugs','Biologics','Devices'][c%3],'Surveillance',classification,
                                 'yes' if adverse else 'no',count,'Quality assurance',text,year])
    rows += [rows[0].copy(), ['SYN-BAD-DATE','SYN-FEI-999','Example Invalid','Example','not-a-date','India','Drugs','Surveillance','OAI','yes',3,'Quality','CAPA',2024],
             ['SYN-UNKNOWN','SYN-FEI-999','Example Unclassified','Example','2025-06-01','India','Drugs','Surveillance','PENDING','', '', 'Quality','',2025]]
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',newline='',encoding='utf-8') as f:
        writer=csv.writer(f); writer.writerow(columns); writer.writerows(rows)
    path.with_suffix('.NOTICE.txt').write_text('SYNTHETIC DEMONSTRATION DATA\nAll companies, sites, FEIs and inspections are fictional.\n',encoding='utf-8')
    return len(rows)

if __name__ == '__main__':
    print(generate(Path('data/sample/synthetic_inspections.csv')))
