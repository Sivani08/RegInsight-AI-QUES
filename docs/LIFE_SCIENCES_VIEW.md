# Life Sciences interpretation of the implementation

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


Business question -> inspection/quality domain classification -> specialist -> source-addressable evidence -> draft interpretation -> model quality check -> expert review -> approved insight for a human business decision.

The supported context is regulatory inspections and quality/compliance evidence. The application does not diagnose patients, classify adverse events, perform pharmacovigilance assessment or authorize product release. Such out-of-scope clinical questions abstain.

InspectionAssessmentAgent explains observation evidence, not official agency findings. DataAnalyticsAgent uses the existing numerical service, retaining denominators and risk coverage. EvidenceAgent explains provided references, whose metadata identify them as supplied/project references rather than automatically approved regulatory authority.

HITL matters because source text can be incomplete, recurring wording can be misleading, and model-generated interpretations can overstate obligations. The backend gate prevents a high judge score from publishing a high-risk artifact without a recorded decision. Human judgment is still required to assess source sufficiency and business context.

This is an auditable local prototype, not a validated regulated system. The judge can err; the default same model can share generation errors. Evidence indexes may be incomplete and lexical search may miss paraphrases. Individual identity, credentialed SME roles, retention, validation/change-control and signed approvals require organization-specific implementation before regulated reliance.
