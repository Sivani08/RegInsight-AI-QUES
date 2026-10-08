"""Versioned rule taxonomy. A match is a text signal, not a confirmed deficiency."""
THEMES={
 'Data Integrity':['data integrity','audit trail','records were deleted','falsif'],
 'OOS Investigation':['oos','out of specification','out-of-specification'],
 'CAPA':['capa','corrective action','preventive action'],
 'Documentation':['documentation','batch records','signatures'],
 'Quality Systems':['quality system','quality unit','quality assurance'],
 'Laboratory Controls':['laboratory','qc','calibration'],
 'Manufacturing Controls':['manufacturing','production control'],
 'Validation':['validation','validated'],
 'Deviation Management':['deviation','root cause'],
 'Training':['training','trained'],
 'Equipment':['equipment','instrument'],
 'Computer Systems':['computer','software','access control'],
}

def themes(text):
    if not text:return []
    lowered=(text or '').lower()
    return [theme for theme,words in THEMES.items() if any(w in lowered for w in words)]

def rule_analysis(text):
    found=themes(text)
    lowered=text.lower()
    severity='Critical' if any(w in lowered for w in ['falsif','records were deleted','contamination']) else 'High' if any(w in lowered for w in ['failed','repeated','disabled']) else 'Medium' if found else 'Low'
    return {'category':'Quality and compliance' if found else 'Unclassified','theme':found[0] if found else 'Unclassified',
            'severity':severity,'confidence':0.65 if found else 0.2,
            'reason':f"Keyword signals: {', '.join(found)}. Human review required; keyword matching does not understand negation." if found else 'No configured theme matched. Human review required.',
            'themes':found,'source':'rules','taxonomy_version':'1.0'}
