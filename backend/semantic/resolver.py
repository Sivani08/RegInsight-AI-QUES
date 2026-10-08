import re
from .catalog import METRICS,COMPOSITE_ALIASES
def resolve(question):
    text=question.casefold()
    if re.search(r'\b(select\s+.+\s+from|drop\s+table|delete\s+from|insert\s+into|union\s+select|update\s+\w+\s+set)\b',text):
        raise ValueError('Use an analytical question; SQL instructions are not accepted.')
    matches=[]
    occupied=[]
    aliases=sorted([(a,m) for m,(_,names) in METRICS.items() for a in names],key=lambda x:-len(x[0]))
    for alias,metric in aliases:
        for match in re.finditer(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',text):
            if not any(match.start()<end and match.end()>start for start,end in occupied):
                occupied.append(match.span())
                if metric not in matches:matches.append(metric)
    for phrase,metrics in COMPOSITE_ALIASES.items():
        if phrase in text:matches=list(dict.fromkeys(metrics+matches))
    if any(p in text for p in ('citation and oai','oai rate','oai rates')) and 'oai_count' in matches:matches.remove('oai_count')
    return matches
