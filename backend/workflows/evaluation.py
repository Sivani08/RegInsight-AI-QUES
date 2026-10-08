from .schemas import JudgeOutput,EvaluationResult
from .policy import ROOT

class EvaluationService:
    def __init__(self,llm,policy):self.llm=llm;self.policy=policy

    def evaluate(self,query,content,evidence,citations,tool_results):
        p=self.policy
        prompt=(ROOT/'config/prompts/workflow_judge.txt').read_text(encoding='utf-8')
        value=self.llm.generate(p.judge_model,prompt,{'query':query,'draft':content,'citations':citations,
            'evidence':[{'chunk_id':r.chunk.chunk_id,'text':r.chunk.chunk_text,'metadata':r.chunk.metadata} for r in evidence],
            'tool_results':tool_results},JudgeOutput,'judge')
        scores=value.dimensions.model_dump();overall=round(sum(scores.values())/len(scores)*10,2)
        hard=scores['groundedness']>=p.judge_min_groundedness and scores['safety']>=p.judge_min_safety
        decision='PASS' if overall>=p.judge_pass_score and hard else 'REVISION_REQUIRED' if overall>=p.judge_revision_score else 'FAIL'
        return EvaluationResult(model=p.judge_model,generation_model=p.generation_model,same_model=p.judge_model==p.generation_model,
            overall_score=overall,decision=decision,dimensions=value.dimensions,issues=value.issues,rationale=value.rationale,
            rubric_version=p.version,thresholds={'pass':p.judge_pass_score,'revision':p.judge_revision_score,
            'minimum_groundedness':p.judge_min_groundedness,'minimum_safety':p.judge_min_safety})
