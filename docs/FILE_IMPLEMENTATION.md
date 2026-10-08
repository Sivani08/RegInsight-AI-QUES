# File implementation and important code

Source of truth: this upgraded project, based on RegInsight-AI-Human-Review.zip. Existing routes and styling remain. New workflows are explicitly started; the legacy chatbot does not silently switch pipelines.


## route

**File:** `backend/workflows/routing.py`

**Lines:** 15-37

**Purpose / why:** Ordered routing, risk, and explicit reason.

**Called by:** WorkflowService.run

**Input:** Structured request and frozen policy

**Output / next stage:** QueryAnalysis and RoutingDecision; consult the workflow diagram for the consuming stage.

```python
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
```

## EmbeddingService

**File:** `backend/rag/embeddings.py`

**Lines:** 4-28

**Purpose / why:** One reproducible representation for documents and queries.

**Called by:** RetrievalService and VectorRepository

**Input:** Text and dimension/model configuration

**Output / next stage:** Normalized vectors; consult the workflow diagram for the consuming stage.

```python
class EmbeddingService:
    model = 'reginsight-hash-v1'
    version = '1.1:word-bigram-signed-l2'
    def __init__(self, dimensions=512, model='reginsight-hash-v1'):
        if model != self.model: raise ValueError('Unsupported workflow embedding model')
        self.dimensions=dimensions

    def embed(self, text):
        words=re.findall(r'[a-z0-9]+',text.casefold())
        stop={'the','a','an','and','or','of','for','to','in','is','are','what','how','this','that','please','explain','summarize','summarise',
              'does','do','did','mean','means','meaning','why','which','where','can','could','would','our','your','it'}
        words=[w for w in words if w not in stop]
        features=words+[a+'_'+b for a,b in zip(words,words[1:])]
        v=[0.0]*self.dimensions
        for token in features:
            h=hashlib.sha256(token.encode()).digest()
            v[int.from_bytes(h[:4],'little')%self.dimensions] += 1 if h[4]&1 else -1
```

## chunk_document

**File:** `backend/rag/chunking.py`

**Lines:** 5-31

**Purpose / why:** Retains source boundaries and metadata while bounding context.

**Called by:** RetrievalService.ingest

**Input:** Source document and policy

**Output / next stage:** Chunk records; consult the workflow diagram for the consuming stage.

```python
def chunk_document(document, policy, embedding):
    """Paragraph/page-aware whitespace windows; long units use bounded overlap.

    Caller passes one PDF page / slide / observation as one document unit.
    Newlines are retained, including extracted table rows. No OCR/table reconstruction.
    """
    text=document['text'].replace('\r\n','\n').strip()
    if len(text)>policy.max_document_characters: raise ValueError('Document exceeds configured character limit')
    document_id=document.get('document_id') or hashlib.sha256((document['name']+'\0'+text).encode()).hexdigest()[:32]
    metadata=document.get('metadata',{})
    result=[]
    for paragraph in re.split(r'\n\s*\n',text):
        spans=list(re.finditer(r'\S+',paragraph))
        start=0
        while start<len(spans):
            end=min(start+policy.chunk_tokens,len(spans))
            part=paragraph[spans[start].start():spans[end-1].end()]
```

## VectorRepository

**File:** `backend/rag/repository.py`

**Lines:** 21-72

**Purpose / why:** Isolates exact vector persistence and filtering.

**Called by:** RetrievalService

**Input:** Chunks or query vector, filters, limit

**Output / next stage:** Stored chunks or scored matches; consult the workflow diagram for the consuming stage.

```python
class VectorRepository:
    def __init__(self,path,embedding,max_chunks=25000):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        self.embedding=embedding;self.max_chunks=max_chunks
        self.space=f'{embedding.model}:{embedding.version}:{embedding.dimensions}'
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS vector_chunks(
              space TEXT,chunk_id TEXT,document_id TEXT,domain TEXT,dataset TEXT,source_type TEXT,
              vector BLOB NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(space,chunk_id));
            CREATE INDEX IF NOT EXISTS vector_metadata ON vector_chunks(space,document_id,domain,dataset,source_type);
            CREATE TABLE IF NOT EXISTS embedding_cache(space TEXT,hash TEXT,vector BLOB,PRIMARY KEY(space,hash));''')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row
        c.create_function('cosine_similarity',2,cosine,deterministic=True)
```

## RetrievalService

**File:** `backend/rag/service.py`

**Lines:** 4-29

**Purpose / why:** Selects evidence and records hit/miss policy.

**Called by:** WorkflowService / indexing CLI

**Input:** Original query and metadata scope

**Output / next stage:** RetrievalTrace; consult the workflow diagram for the consuming stage.

```python
class RetrievalService:
    def __init__(self, repository, policy):
        self.repository=repository;self.embedding=repository.embedding;self.policy=policy

    def ingest(self,document):
        return self.repository.upsert_document(chunk_document(document,self.policy,self.embedding))

    def search(self,query,query_id,filters=None):
        p=self.policy;filters=filters or {}
        results=self.repository.search(self.embedding.embed_query(query),filters,p.retrieval_candidate_limit)
        best=results[0].similarity_score if results else 0
        status='STRONG_HIT' if best>=p.strong_hit_threshold else 'WEAK_HIT' if best>=p.weak_hit_threshold else 'MISS'
        selected=[r.chunk.chunk_id for r in results if r.similarity_score>=p.weak_hit_threshold][:p.retrieval_top_k]
        return RetrievalTrace(query_id=query_id,query=query,embedding_model=self.embedding.model,
            embedding_version=self.embedding.version,embedding_dimensions=self.embedding.dimensions,filters=filters,
            top_k=p.retrieval_top_k,thresholds={'strong':p.strong_hit_threshold,'weak':p.weak_hit_threshold},
            results=results,final_chunk_ids=selected,retrieval_status=status)
```

## StructuredLLM

**File:** `backend/libraries/structured_llm.py`

**Lines:** 10-35

**Purpose / why:** Bounded local model transport without business policy.

**Called by:** Specialists and EvaluationService

**Input:** Model, system prompt, JSON input and schema

**Output / next stage:** Validated Pydantic model; consult the workflow diagram for the consuming stage.

```python
class StructuredLLM:
    """Loopback-only schema client. Each judge invocation is an actual model call."""
    def __init__(self,timeout=120): self.timeout=timeout;self.calls=deque(maxlen=100)

    @property
    def last_call(self):return _last_call.get()

    def generate(self,model,system,payload,schema,purpose):
        if not re.fullmatch(r'[a-zA-Z0-9_.:/-]{1,150}',model) or 'cloud' in model.casefold():raise ValueError('Downloaded local model required')
        raw=json.dumps(payload,ensure_ascii=False)
        if len(raw)>60000:raise ValueError('Prompt context exceeds local bound')
        if not _gate.acquire(blocking=False):raise RuntimeError('Local workflow model busy; retry later')
        started=time.monotonic()
        try:
            with httpx.Client(trust_env=False,timeout=httpx.Timeout(self.timeout,connect=3)) as client:
                r=client.post(local_origin()+'/api/chat',json={'model':model,'stream':False,'think':False,
                    'messages':[{'role':'system','content':system},{'role':'user','content':raw}],
```

## EvidenceAgent

**File:** `backend/agents/specialists.py`

**Lines:** 6-26

**Purpose / why:** Standard specialist interface; validates citations and numeric support.

**Called by:** WorkflowService.run

**Input:** AgentInput with evidence, tools and revision comments

**Output / next stage:** AgentResult; consult the workflow diagram for the consuming stage.

```python
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
```

## EvaluationService

**File:** `backend/workflows/evaluation.py`

**Lines:** 4-19

**Purpose / why:** Separate judge call and configurable score gates.

**Called by:** WorkflowService.run

**Input:** Draft, query, citations, evidence, tools

**Output / next stage:** EvaluationResult; consult the workflow diagram for the consuming stage.

```python
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
```

## WorkflowRepository

**File:** `backend/workflows/repository.py`

**Lines:** 8-52

**Purpose / why:** Durable pause state and concurrency checks.

**Called by:** WorkflowService / APIs

**Input:** Typed state plus expected revision

**Output / next stage:** Persisted state and ordered events; consult the workflow diagram for the consuming stage.

```python
class WorkflowRepository:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as c:
            c.executescript('''PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS workflows(id TEXT PRIMARY KEY,status TEXT,revision INTEGER,payload TEXT);
            CREATE TABLE IF NOT EXISTS workflow_events(workflow_id TEXT,sequence INTEGER,event TEXT,payload TEXT,created_at TEXT,PRIMARY KEY(workflow_id,sequence));
            CREATE INDEX IF NOT EXISTS workflow_status ON workflows(status);''')

    @contextmanager
    def connect(self):
        c=sqlite3.connect(self.path,timeout=15)
        try:
            with c:yield c
        finally:c.close()

    def create(self,state):
```

## run

**File:** `backend/workflows/service.py`

**Lines:** 42-127

**Purpose / why:** Routes, retrieves, generates, judges and stops at the gate.

**Called by:** POST workflows background task / resume

**Input:** Workflow ID

**Output / next stage:** WorkflowState; consult the workflow diagram for the consuming stage.

```python
    def run(self,identifier):
        state=self.repository.get(identifier)
        if state.status=='APPROVED':return self.finalize(state)
        if state.status not in ('RECEIVED','REVISION_REQUIRED'):raise Conflict('Workflow cannot run in its current state')
        p=Policy(**state.policy);started=time.monotonic()
        # Policy is snapshotted per workflow; retrieval settings and model IDs stay stable on resume.
        from backend.rag.service import RetrievalService
        retrieval=RetrievalService(self.retrieval.repository,p)
        if p.embedding_dimensions!=retrieval.embedding.dimensions or p.embedding_model!=retrieval.embedding.model:
            raise Conflict('Workflow embedding configuration changed; restore its index configuration')
        if state.retrieval_trace and state.retrieval_trace.embedding_version!=retrieval.embedding.version:
            raise Conflict('Embedding preprocessing changed; use the matching version to resume')
        if state.iteration>=p.maximum_agent_iterations:raise Conflict('Maximum workflow iterations reached')
        state.analysis,state.routing=route(state.request,p)
        state=self.checkpoint(state,'ROUTED','routing',state.routing.model_dump())
        try:
            if state.routing.selected_agent=='UnsupportedDomainAgent':
```

## review

**File:** `backend/workflows/service.py`

**Lines:** 140-155

**Purpose / why:** Applies a version-matched human decision.

**Called by:** Review API

**Input:** Workflow ID, action, reviewer, comment and artifact version

**Output / next stage:** Updated state / approved final; consult the workflow diagram for the consuming stage.

```python
    def review(self,identifier,decision,body):
        state=self.repository.get(identifier)
        if state.status!='AWAITING_HUMAN_REVIEW' or not state.artifacts:raise Conflict('No pending human gate')
        a=state.artifacts[-1]
        if body.artifact_version!=a.version:raise Conflict('Artifact version changed; review the latest version')
        if decision not in ('APPROVED','REVISION_REQUIRED','REJECTED'):raise ValueError('Unknown decision')
        if decision=='REVISION_REQUIRED' and state.iteration>=state.policy['maximum_agent_iterations']:
            raise Conflict('Revision limit reached; reject and start a new request if needed')
        a.review_status=decision
        record={'reviewer':body.reviewer,'comment':body.comment,'decision':decision,'timestamp':now(),
            'artifact_id':a.artifact_id,'artifact_version':a.version,'previous_version':a.previous_version,
            'evaluation_score':a.evaluation.overall_score,'previous_state':state.status,'workflow_state':decision,
            'identity':'Self-reported local reviewer; not an authenticated SME signature'}
        state.reviews.append(record)
        state=self.checkpoint(state,decision,'human_decision',record)
        return self.finalize(state) if decision=='APPROVED' else state
```

## finalize

**File:** `backend/workflows/service.py`

**Lines:** 129-138

**Purpose / why:** Prevents publication without evaluation and mandatory approval.

**Called by:** run or approve

**Input:** Current persisted workflow state

**Output / next stage:** COMPLETED state; consult the workflow diagram for the consuming stage.

```python
    def finalize(self,state):
        if not state.artifacts:raise Conflict('No evaluated artifact')
        a=state.artifacts[-1]
        if a.evaluation.decision!='PASS':raise Conflict('Evaluation has not passed')
        if a.review_required and (state.status!='APPROVED' or a.review_status!='APPROVED'):
            raise Conflict('Mandatory human approval is pending')
        if state.status not in ('APPROVED','EVALUATING'):raise Conflict('Invalid finalization state')
        # No unreviewed LLM call after approval. Publish exactly the approved artifact.
        state.final_response=a.content
        return self.checkpoint(state,'COMPLETED','finalized',{'artifact_id':a.artifact_id,'artifact_version':a.version})
```

## create_workflows

**File:** `backend/workflows/factory.py`

**Lines:** 12-20

**Purpose / why:** Wires existing analytics with new isolated stores.

**Called by:** FastAPI lifespan

**Input:** Existing inspection service

**Output / next stage:** WorkflowService; consult the workflow diagram for the consuming stage.

```python
def create_workflows(inspection_service):
    policy=load_policy()
    folder=Path(os.getenv('WORKFLOW_DATA_DIR') or ROOT/'data/workflows')
    embedding=EmbeddingService(policy.embedding_dimensions,policy.embedding_model)
    retrieval=RetrievalService(VectorRepository(folder/'vectors.db',embedding,policy.max_index_chunks),policy)
    # Explicit idempotent seed from bundled curated knowledge, no provider call or network.
    retrieval.seed_references(ROOT)
    return WorkflowService(WorkflowRepository(folder/'workflows.db'),retrieval,
        StructuredLLM(policy.llm_timeout_seconds),policy,DashboardInsights(inspection_service))
```

## Other important files

- `backend/workflows/schemas.py`: strict state, chunk, artifact, judge and review contracts.
- `backend/workflows/policy.py`: configuration validation and snapshot loading.
- `config/workflow_policy.json`: thresholds, bounds, model choices.
- `config/prompts/workflow_generation.txt`: generation and revision rules.
- `config/prompts/workflow_judge.txt`: scored evaluation rubric.
- `backend/api/workflows.py`: create/status/retrieval/evaluation/trace/review/resume endpoints.
- `frontend/src/reginsight/WorkflowReview.jsx`: existing-section diagnostic/review interface.
- `frontend/src/reginsight/Evidence.jsx`: one import and panel mount; existing decisions retained.
- `scripts/index_workflow_sources.py`: explicit PDF/PPTX/text reference indexing.
- `scripts/evaluate_workflows.py`: measured routing/retrieval development evaluation.
- `tests/test_workflows.py`: isolated integration and gate coverage.
