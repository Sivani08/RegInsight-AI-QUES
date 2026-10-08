"""Standard-contract specialists; explicit bounded invocation by WorkflowService."""
import re
from backend.workflows.schemas import AgentInput, AgentResult, GeneratedDraft
from backend.workflows.policy import ROOT

class EvidenceAgent:
    name='EvidenceAgent'
    role='Summarize relevant project or regulatory reference evidence; disclose authority limits.'
    def __init__(self,llm,policy):self.llm=llm;self.policy=policy

    def run(self,body:AgentInput,requires_review=False):
        sources=[{'chunk_id':r.chunk.chunk_id,'text':r.chunk.chunk_text,'document':r.chunk.document_name,
                  'metadata':r.chunk.metadata} for r in body.evidence]
        prompt=(ROOT/'config/prompts/workflow_generation.txt').read_text(encoding='utf-8')
        value=self.llm.generate(self.policy.generation_model,prompt,{'agent_role':self.role,'query':body.query,
            'evidence':sources,'tool_results':body.tool_results,'reviewer_comment':body.revision_comment,
            'previous_draft':body.previous_content},GeneratedDraft,'generation:'+self.name)
        ids={r.chunk.chunk_id for r in body.evidence}|({'D1'} if body.tool_results else set())
        if not value.citations or any(c not in ids for c in value.citations):raise ValueError('Draft contains unsupported citations')
        import json
        support=' '.join(r.chunk.chunk_text for r in body.evidence if r.chunk.chunk_id in value.citations)
        if 'D1' in value.citations:support+=' '+json.dumps(body.tool_results)
        nums=lambda s:set(re.findall(r'(?<!\w)\d+(?:\.\d+)?',s.replace(',','')))
        if not nums(value.content).issubset(nums(support)):raise ValueError('Draft contains unsupported numbers')
        return AgentResult(agent_name=self.name,status='GENERATED',answer=value.content,evidence=value.citations,
            limitations=value.limitations,requires_human_review=requires_review,next_recommended_action='EVALUATE')

class InspectionAssessmentAgent(EvidenceAgent):
    name='InspectionAssessmentAgent'
    role='Explain inspection observations, quality themes and evidence limitations. Do not certify compliance or infer clinical harm.'

class DataAnalyticsAgent(EvidenceAgent):
    name='DataAnalyticsAgent'
    role='Explain the supplied D1 calculated result. Never compute or invent counts, rates, risk, or denominators.'

AGENTS={a.name:a for a in (EvidenceAgent,InspectionAssessmentAgent,DataAnalyticsAgent)}
