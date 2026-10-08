"""Observation taxonomy v2.1; v1 risk taxonomy is deliberately unchanged."""
import re
from backend.analytics.taxonomy import THEMES as RISK_THEMES
VERSION='2.2'
THEMES={k:list(v) for k,v in RISK_THEMES.items()}
THEMES['Data Integrity']+=['contemporaneous','retrospectiv','after testing','original data','original records','backdat','records were not retained','unreliable original records']
THEMES.update({'Materials Management':['raw material','component receipt','supplier qualification','incoming material'], 'Packaging and Labeling':['labeling','labelling','packaging','label control'], 'Cleaning and Sanitation':['sanitation','sanitary','cleaning','pest','vermin'], 'Complaints':['complaint'], 'Investigations':['investigat'], 'Environmental Monitoring':['environmental monitoring','environmental sample'], 'Sterility Assurance':['steril','aseptic','microbial contamination'], 'Production and Process Controls':['process control','in-process control'], 'Equipment and Facilities':['facility','facilities','building','maintenance']})
THEME_NAMES=tuple(THEMES)+('Unclassified',)
def normalize(text):return ' '.join(str(text or '').split())
def is_instruction(text):
    return bool(re.search(r'ignore (?:all |the |any )?(?:previous|prior|system) instructions|classify (?:this|it|everything) as|system prompt|you are (?:now |an? )|return (?:only )?json',text,re.I))

def supported_theme(theme,text):
    if theme=='Unclassified':return True
    if any(x in text.lower() for x in ['no evidence of','no deficiencies','did not fail','not observed']):return False
    return any(word in text.lower() for word in THEMES.get(theme,[]))

def severity_supported(severity,text):
    low=text.lower()
    if severity in ('Low','Medium','Unclassified'):return True
    if any(x in low for x in ['no evidence of','no deficiencies','not observed']):return False
    critical=any(x in low for x in ['falsif','records were deleted','unreliable original records','contaminated released product','serious contamination','released contaminated'])
    if severity=='Critical':return critical
    return critical or any(x in low for x in ['significant','systemic','repeated','disabled','not retained','no investigation','not established'])

def rules(text):
    text=normalize(text)
    if not text:raise ValueError('Empty observation')
    parts=re.split(r'(?<=[.!?])\s+',text)
    for part in parts:
        low=part.lower()
        if is_instruction(part) or any(x in low for x in ['no evidence of','no deficiencies','did not fail','not observed']):continue
        matches=[(t,w) for t,ws in THEMES.items() for w in ws if w in low]
        if matches:
            theme=matches[0][0]
            at=low.find(matches[0][1]);start=max(0,at-100);quote=part[start:start+900]
            severity='Critical' if severity_supported('Critical',quote) else 'High' if severity_supported('High',quote) else 'Low' if 'isolated' in low and 'no product impact' in low else 'Medium'
            return {'category':'Quality and compliance','theme':theme,'severity':severity,'confidence':0.55,'evidence_quote':quote,'rationale':f'Rule-based {theme} text signal. {severity} analytical priority follows explicit words in the quoted passage; confidence is heuristic, not calibrated.','keywords':list(dict.fromkeys(w for _,w in matches))[:20]}
    return {'category':'Unclassified','theme':'Unclassified','severity':'Unclassified','confidence':0.1,'evidence_quote':text[:900],'rationale':'No supported taxonomy signal. Insufficient evidence for analytical severity; human review required.','keywords':[]}
