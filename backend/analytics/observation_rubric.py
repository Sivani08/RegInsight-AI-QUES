"""Versioned observation interpretation rubric, separate from numeric risk taxonomy."""
import re
from backend.analytics.taxonomy import THEMES
VERSION='2.0'
CATEGORY_MAP={'Data Integrity':'Records and data integrity','Documentation':'Records and data integrity','Computer Systems':'Records and data integrity','OOS Investigation':'Laboratory controls','Laboratory Controls':'Laboratory controls','CAPA':'Quality management','Quality Systems':'Quality management','Deviation Management':'Quality management','Training':'Personnel and training','Validation':'Production and validation','Manufacturing Controls':'Production and validation','Equipment':'Facilities and equipment'}
CATEGORIES=sorted(set(CATEGORY_MAP.values()))+['Unclassified']
SEVERITIES=['Low','Medium','High','Critical','Insufficient evidence']
RUBRIC={'Critical':'Explicit falsification, deleted original records, or contamination affecting released product.','High':'Explicit failed, repeated, disabled or missing investigation/control.','Medium':'Identified incomplete or inadequate control without an explicit higher-severity signal.','Low':'Explicit isolated administrative issue with stated absence of product impact.','Insufficient evidence':'No supported deficiency, ambiguous or negated text, or too little context.'}
def tag_rules(text):
    sentences=[x.strip() for x in re.split(r'(?<=[.!?])\s+',text) if x.strip()]
    hits=[]
    for sentence in sentences:
        low=sentence.lower()
        # Conservative abstention: negation is difficult; do not turn a negative statement into a finding.
        if re.search(r'\b(no evidence|no deficiencies|no failures|did not fail|not observed|without deficiencies)\b',low):continue
        for theme,words in THEMES.items():
            if any(w in low for w in words):hits.append((theme,sentence))
    found=list(dict.fromkeys(t for t,_ in hits));quotes=list(dict.fromkeys(s for _,s in hits))
    text=' '.join(quotes).lower()
    severity='Insufficient evidence'
    if found:
        if any(x in text for x in ['falsif','records were deleted','contaminated released product']):severity='Critical'
        elif any(x in text for x in ['failed','repeated','disabled','no investigation']):severity='High'
        elif 'isolated administrative' in text and 'no product impact' in text:severity='Low'
        elif any(x in text for x in ['incomplete','inadequate','lacked','not verified','not establish']):severity='Medium'
    return {'category':CATEGORY_MAP.get(found[0],'Unclassified') if found else 'Unclassified','themes':found,'theme':found[0] if found else 'Unclassified','severity':severity,'evidence_quotes':quotes,'confidence':None,'source':'rules','model':None,'rubric_version':VERSION,'review_status':'pending','reason':RUBRIC[severity]}
