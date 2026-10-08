# Human-in-the-loop and SME workflow

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


The new gate is distinct from the existing append-only observation decision. Existing Approve/Modify/Reject controls keep their behavior. The added collapsed panel reviews versioned AI assessment artifacts.

```
Query -> rubric -> retrieve/tools -> specialist draft -> LLM judge
 PASS + required review -> AWAITING_HUMAN_REVIEW (final_response is null)
 Approve -> APPROVED -> publish exact approved artifact -> COMPLETED
 Request revision -> REVISION_REQUIRED -> original agent + comment -> judge -> new gate
 Reject -> REJECTED (no final assessment)
```

Reviewer sees query, selected agent/reason, risk, draft version, evidence candidates and selected chunks, model scores/issues, source metadata, reviewer history and final response only after release. Agent confidence is explicitly uncalibrated, not invented.

Backend enforcement: `WorkflowService.finalize()` requires PASS; mandatory review additionally requires APPROVED workflow and APPROVED latest artifact. `/resume` refuses AWAITING_HUMAN_REVIEW. Review requires matching artifact_version, reviewer and nonblank rationale. Repository writes compare state revisions in a BEGIN IMMEDIATE transaction. A stale decision returns 409. Finalization makes no new model call.

Review records include reviewer, timestamp, decision, comment, artifact ID/version, previous version, score, previous state and resulting state. Artifact versions and previous evidence are preserved. A new process reconstructs pending workflow state from SQLite. In-flight generation interrupted by process loss is not automatically restarted: the operator should inspect the state and start a new request; this prototype has no distributed lease/worker recovery scheduler.

Identity remains self-reported under the existing local/shared-key access system. No SME credential verification, individual RBAC, immutable cryptographic audit or electronic-signature compliance is claimed. Do not use automated demo approval as a real human endorsement.

Policies apply to inspection/quality work, not a fabricated clinical or pharmacovigilance capability. High-risk suggestions always require review; a judge cannot certify regulatory validity.
