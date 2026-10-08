from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.semantic.models import Filters

def now():
    return datetime.now(timezone.utc).isoformat()

class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')

class WorkflowRequest(Strict):
    question: str = Field(min_length=3, max_length=4000)
    filters: dict[str, str] = Field(default_factory=dict)
    observation_id: str | None = Field(default=None, max_length=512)
    run_id: str | None = Field(default=None, max_length=100)
    require_review: bool = False
    analytics_filters: Filters = Field(default_factory=Filters)

    @field_validator('question')
    @classmethod
    def nonblank(cls, value):
        if len(value.strip()) < 3: raise ValueError('Enter a substantive question')
        return value.strip()

    @field_validator('filters')
    @classmethod
    def allowed(cls, value):
        if set(value) - {'dataset', 'domain', 'document_id', 'source_type', 'company', 'site', 'year', 'inspection_type', 'classification', 'severity', 'theme', 'source', 'observation_id'}:
            raise ValueError('Unsupported retrieval filter')
        if any(not v.strip() or len(v) > 512 for v in value.values()):
            raise ValueError('Invalid filter')
        return value

class QueryAnalysis(Strict):
    query: str
    domain: Literal['Regulatory', 'Quality', 'Analytics', 'General']
    task_type: Literal['Search', 'Summarise', 'Analyse', 'Compare', 'Recommend']
    risk_level: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    required_agents: list[str]
    requires_rag: bool
    requires_tools: bool
    requires_hitl: bool

class RoutingDecision(Strict):
    selected_agent: str
    secondary_agents: list[str] = Field(default_factory=list)
    routing_reason: str
    matched_rules: list[str]
    rubric_version: str
    rubric: dict
    confidence: float | None = None  # No invented probability for a rule decision.

class Chunk(Strict):
    chunk_id: str
    document_id: str
    document_name: str
    source_type: str
    domain: str
    section: str | None = None
    page_number: int | None = None
    chunk_index: int
    chunk_text: str
    token_count: int
    token_count_method: str = 'regex_nonwhitespace_v1'
    metadata: dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=now)
    embedding_model: str
    embedding_version: str

class RetrievedChunk(Strict):
    chunk: Chunk
    similarity_score: float = Field(ge=-1.00001, le=1.00001)
    rank: int
    reranking_score: float | None = None

class RetrievalTrace(Strict):
    search_details: dict = Field(default_factory=dict)
    query_id: str
    query: str
    rewritten_query: str | None = None
    embedding_model: str
    embedding_version: str
    embedding_dimensions: int
    filters: dict
    top_k: int
    thresholds: dict
    results: list[RetrievedChunk]
    final_chunk_ids: list[str]
    retrieval_status: Literal['STRONG_HIT', 'WEAK_HIT', 'MISS']
    confidence: float | None = None
    score_interpretation: str = 'Cosine similarity, not calibrated confidence'

class AgentInput(Strict):
    query: str
    evidence: list[RetrievedChunk]
    tool_results: dict = Field(default_factory=dict)
    revision_comment: str | None = None
    previous_content: str | None = None

class GeneratedDraft(Strict):
    content: str = Field(min_length=1, max_length=10000)
    citations: list[str] = Field(max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=12)

class AgentResult(Strict):
    agent_name: str
    status: Literal['GENERATED', 'ABSTAINED']
    answer: str
    evidence: list[str]
    limitations: list[str]
    confidence: float | None = None
    requires_human_review: bool
    next_recommended_action: str

class JudgeScores(Strict):
    relevance: float = Field(ge=0, le=10)
    groundedness: float = Field(ge=0, le=10)
    factual_consistency: float = Field(ge=0, le=10)
    completeness: float = Field(ge=0, le=10)
    domain_correctness: float = Field(ge=0, le=10)
    safety: float = Field(ge=0, le=10)
    evidence_coverage: float = Field(ge=0, le=10)
    clarity: float = Field(ge=0, le=10)

class JudgeOutput(Strict):
    dimensions: JudgeScores
    issues: list[str] = Field(default_factory=list, max_length=20)
    rationale: str = Field(min_length=1, max_length=2000)

class EvaluationResult(Strict):
    model: str
    generation_model: str
    same_model: bool
    overall_score: float
    decision: Literal['PASS', 'REVISION_REQUIRED', 'FAIL']
    dimensions: JudgeScores
    issues: list[str]
    rationale: str
    rubric_version: str
    thresholds: dict
    evaluated_at: str = Field(default_factory=now)

class Artifact(Strict):
    artifact_id: str
    workflow_id: str
    version: int
    previous_version: int | None
    agent: str
    artifact_type: str = 'inspection_evidence_assessment'
    content: str
    evidence: list[str]
    limitations: list[str]
    risk_level: str
    review_required: bool
    review_status: Literal['PENDING', 'APPROVED', 'REVISION_REQUIRED', 'REJECTED', 'NOT_REQUIRED']
    evaluation: EvaluationResult
    created_at: str = Field(default_factory=now)

class ReviewDecision(Strict):
    workflow_revision: int = Field(ge=0)
    idempotency_key: str = Field(min_length=8, max_length=100)
    modified_output: str | None = Field(default=None, min_length=1, max_length=10000)
    artifact_version: int = Field(ge=1)
    reviewer: str = Field(min_length=1, max_length=100)
    comment: str = Field(min_length=1, max_length=2000)

    @field_validator('reviewer', 'comment')
    @classmethod
    def nonblank(cls, v):
        if not v.strip(): raise ValueError('Nonblank reviewer and rationale required')
        return v.strip()

class WorkflowState(Strict):
    user_id: str
    session_id: str
    workflow_id: str
    request_id: str
    request: WorkflowRequest
    status: Literal['RECEIVED','ROUTED','RETRIEVING','GENERATING','EVALUATING',
                    'AWAITING_HUMAN_REVIEW','REVISION_REQUIRED','APPROVED','COMPLETED','FAILED','REJECTED']
    revision: int = 0
    iteration: int = 0
    analysis: QueryAnalysis | None = None
    routing: RoutingDecision | None = None
    retrieval_trace: RetrievalTrace | None = None
    retrieval_history: list[RetrievalTrace] = Field(default_factory=list)
    tool_results: dict = Field(default_factory=dict)
    agent_outputs: list[AgentResult] = Field(default_factory=list)
    artifacts: list[Artifact] = Field(default_factory=list)
    reviews: list[dict] = Field(default_factory=list)
    final_response: str | None = None
    error: str | None = None
    policy: dict
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
