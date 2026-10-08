# Routing rubric

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


`backend/workflows/routing.py` is an ordered decision table. It persists selected agent, secondary agents, matched rule IDs, reason, domain, task, data requirement and risk. Confidence is null: there is no calibrated routing probability.

| Rule | Condition | Result |
|---|---|---|
| R1 | Patient/dose/diagnosis/treatment/pharmacovigilance/adverse-event request | Unsupported-domain abstention |
| R2 | How many/count/rate/trend/compare/highest/lowest/total/distribution | DataAnalyticsAgent with existing SQL service |
| R3 | Selected observation or observation/finding/CAPA/deficiency/quality/compliance/inspection | InspectionAssessmentAgent |
| R4 | Other reference explanation/search | EvidenceAgent |
| M1 | R2 and R3 both match | Analytics primary, assessment secondary |
| H1 | Recommendation/should/approve/release/compliant/certification/regulatory significance or impact | HIGH risk, mandatory review |
| H1 critical | Patient harm/falsification/contamination/critical/safety | CRITICAL risk, mandatory review |
| H2 | Explicit review request or weak retrieval | Mandatory review |

Observation interpretation is otherwise MEDIUM; reference explanation is LOW. Tasks resolve to Recommend, Compare, Analyse, Summarise or Search. Ordering is explicit; user input cannot submit a preferred agent, judge result or approval state. Risk labels are conservative routing policy, not regulatory determinations. Keyword rules can over/under-route and are not a clinical risk model.

Policy: `config/workflow_policy.json`; high/critical review cannot be disabled by invalid configuration. Query schemas forbid extra fields. The 12-case development routing evaluation is in `workflow-evaluation-results.json`; do not generalize its accuracy to production.
