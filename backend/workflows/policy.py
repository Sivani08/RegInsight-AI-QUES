import json, os
from pathlib import Path
from pydantic import Field, model_validator
from .schemas import Strict

ROOT = Path(__file__).resolve().parents[2]

class Policy(Strict):
    version: str = '1.0'
    embedding_model: str = 'nomic-embed-text:latest'
    embedding_dimensions: int | None = Field(None, ge=1, le=4096)
    generation_model: str = 'reginsight-chat:qwen3-1.7b'
    judge_model: str = 'reginsight-chat:qwen3-1.7b'
    retrieval_top_k: int = Field(5, ge=1, le=10)
    retrieval_candidate_limit: int = Field(20, ge=1, le=100)
    strong_hit_threshold: float = Field(.65, gt=0, le=1)
    weak_hit_threshold: float = Field(.55, ge=0, lt=1)
    judge_pass_score: float = Field(80, ge=0, le=100)
    judge_revision_score: float = Field(60, ge=0, le=100)
    judge_min_groundedness: float = Field(7, ge=0, le=10)
    judge_min_safety: float = Field(7, ge=0, le=10)
    mandatory_hitl_risk_levels: list[str] = ['HIGH', 'CRITICAL']
    maximum_agent_iterations: int = Field(3, ge=1, le=5)
    chunk_tokens: int = Field(220, ge=30, le=500)
    chunk_overlap: int = Field(30, ge=0)
    max_index_chunks: int = Field(25000, ge=1, le=100000)
    max_document_characters: int = Field(200000, ge=100, le=1000000)
    llm_timeout_seconds: int = Field(120, ge=1, le=300)

    @model_validator(mode='after')
    def coherent(self):
        if self.chunk_overlap >= self.chunk_tokens: raise ValueError('Overlap must be smaller than chunk size')
        if self.weak_hit_threshold >= self.strong_hit_threshold: raise ValueError('Invalid retrieval thresholds')
        if self.judge_revision_score >= self.judge_pass_score: raise ValueError('Invalid judge thresholds')
        if self.retrieval_candidate_limit < self.retrieval_top_k: raise ValueError('Candidate limit below top-k')
        if not {'HIGH','CRITICAL'}.issubset(self.mandatory_hitl_risk_levels): raise ValueError('High-risk review cannot be disabled')
        return self

def load_policy():
    p=json.loads((ROOT/'config/workflow_policy.json').read_text(encoding='utf-8'))
    for env,key in [('WORKFLOW_GENERATION_MODEL','generation_model'),('WORKFLOW_JUDGE_MODEL','judge_model')]:
        if os.getenv(env): p[key]=os.environ[env]
    return Policy(**p)
