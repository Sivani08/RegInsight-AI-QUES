"""Ordered decision table; no pseudo-probability or undocumented route scores."""
import re
from .schemas import QueryAnalysis, RoutingDecision

RUBRIC = {
 'R1': 'Unsupported clinical/patient or pharmacovigilance advice -> abstain; no such specialist in this project.',
 'R2': 'Inspection counts, rates, comparison or trends -> DataAnalyticsAgent; numerical authority stays in existing SQL.',
 'R3': 'Observation, finding, CAPA, quality/compliance, inspection interpretation -> InspectionAssessmentAgent.',
 'R4': 'Project/regulatory reference search or explanation -> EvidenceAgent.',
 'H1': 'Recommendations, compliance approval, release decisions, safety or critical impact -> mandatory review.',
 'H2': 'Explicit user review request or weak retrieval -> mandatory review.',
 'M1': 'Combined analytics and observation interpretation -> analytics primary, assessment secondary, bounded sequential execution.'
}

def route(request,policy):
    q=request.question.casefold();matched=[]
    unsupported=bool(re.search(r'\b(patient|dosage|dose|diagnos\w*|treatment|pharmacovigilance|adverse.event)\b',q))
    analytic=bool(re.search(r'\b(how many|count|rate|trend|compare|highest|lowest|total|distribution)\b',q))
    assessment=bool(request.observation_id or re.search(r'\b(observations?|findings?|capa|deficien\w*|quality|compliance|inspections?)\b',q))
    recommend=bool(re.search(r'\b(recommend\w*|should|approve|release|compliant|certif\w*|regulatory significance|regulatory impact)\b',q))
    critical=bool(re.search(r'\b(patient harm|falsif\w*|contamination|critical|safety)\b',q))
    risk='CRITICAL' if critical else 'HIGH' if recommend else 'MEDIUM' if assessment else 'LOW'
    if unsupported: selected='UnsupportedDomainAgent';secondary=[];matched=['R1'];domain='General'
    elif analytic:
        selected='DataAnalyticsAgent';secondary=['InspectionAssessmentAgent'] if assessment else [];matched=['R2']+(['M1','R3'] if secondary else []);domain='Analytics'
    elif assessment:selected='InspectionAssessmentAgent';secondary=[];matched=['R3'];domain='Quality'
    else:selected='EvidenceAgent';secondary=[];matched=['R4'];domain='Regulatory'
    human=risk in policy.mandatory_hitl_risk_levels or request.require_review
    if risk in policy.mandatory_hitl_risk_levels:matched.append('H1')
    if request.require_review:matched.append('H2')
    task='Recommend' if recommend else 'Compare' if 'compare' in q else 'Analyse' if analytic or assessment else 'Summarise' if re.search(r'summari[sz]',q) else 'Search'
    analysis=QueryAnalysis(query=request.question,domain=domain,task_type=task,risk_level=risk,
        required_agents=[selected,*secondary],requires_rag=not unsupported,requires_tools=analytic and not unsupported,requires_hitl=human)
    decision=RoutingDecision(selected_agent=selected,secondary_agents=secondary,routing_reason=' '.join(RUBRIC[m] for m in matched),
        matched_rules=matched,rubric_version=policy.version,rubric={'method':'ordered_decision_table','domain':domain,
        'task':task,'data_requirement':'SQL+vectors' if analysis.requires_tools else 'vectors','risk':risk,'review':'MANDATORY' if human else 'NONE'})
    return analysis,decision
