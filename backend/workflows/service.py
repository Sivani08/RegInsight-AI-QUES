"""RegInsight workflow stages, evaluated artifacts and authenticated review transitions."""
import json
import logging
import re
import uuid
from psycopg.types.json import Jsonb
from backend.database.postgres import connection, database_url
from backend.agents.specialists import AGENTS
from .schemas import WorkflowState, Artifact, AgentInput, now
from .policy import Policy
from .routing import route
from .evaluation import EvaluationService
from .repository import Conflict
from .jobs import enqueue

log=logging.getLogger(__name__)


class WorkflowService:
    def __init__(self, repository, retrieval, llm, policy, analytics=None):
        self.repository=repository
        self.retrieval=retrieval
        self.llm=llm
        self.policy=policy
        self.analytics=analytics

    def create(self, request, principal):
        state=WorkflowState(workflow_id=str(uuid.uuid4()),request_id=str(uuid.uuid4()),request=request,
            user_id=principal.user_id,session_id=principal.session_id,status='RECEIVED',policy=self.policy.model_dump())
        with connection() as current:
            self.repository.create(state,current)
            enqueue(current,state.user_id,state.workflow_id,{},'start:'+state.workflow_id)
        return state

    def checkpoint(self,state,status,event,detail=None):
        latest=self.repository.get(state.workflow_id)
        if latest.revision>state.revision:
            events=self.repository.events(state.workflow_id)
            if events[-1]['event']==event:
                return latest
            raise Conflict('Unexpected workflow revision during recovery')
        state.status=status
        saved=self.repository.save(state,event,detail)
        log.info('workflow_node workflow_id=%s user_id=%s request_id=%s node=%s revision=%s',
            saved.workflow_id,saved.user_id,saved.request_id,event,saved.revision)
        return saved

    def determine_route(self,state):
        state.analysis,state.routing=route(state.request,Policy(**state.policy))
        if state.routing.selected_agent=='UnsupportedDomainAgent':
            state.final_response='This workflow supports inspection and quality evidence, not patient-specific or pharmacovigilance advice.'
            return self.checkpoint(state,'COMPLETED','unsupported_domain')
        return self.checkpoint(state,'ROUTED','routing',state.routing.model_dump())

    def selected_observation(self,request):
        if not request.observation_id:
            return None
        from backend.services.observation_intelligence import tags
        page=tags(observation_id=request.observation_id,run_id=request.run_id,limit=1)
        if not page.records:
            raise ValueError('Selected observation unavailable')
        request.run_id=page.run_id
        record=page.records[0]
        document_id='observation:'+str(page.run_id)+':'+record.observation_id
        self.retrieval.ingest({'document_id':document_id,'name':record.source_file,'text':record.original_text,
            'source_type':'observation','domain':'Quality','metadata':{'dataset':record.dataset,
            'observation_id':record.observation_id,'inspection_id':record.inspection_id,
            'source_sheet':record.source_sheet,'source_row':record.source_row,'run_id':page.run_id}})
        return document_id

    def retrieve_evidence(self,state):
        filters=dict(state.request.filters)
        document_id=self.selected_observation(state.request)
        if document_id:
            if filters.get('document_id') and filters['document_id']!=document_id:
                raise ValueError('Conflicting observation scope')
            filters['document_id']=document_id
        trace=self.retrieval.search(state.request.question,state.request_id,filters)
        state.retrieval_trace=trace
        state.retrieval_history.append(trace.model_copy(deep=True))
        if state.analysis.requires_tools:
            from backend.semantic.models import QueryRequest
            from backend.agents.chatbot import compact_dashboard_evidence
            result=self.analytics.query(QueryRequest(question=state.request.question,filters=state.request.analytics_filters,limit=3))
            state.tool_results={'D1':json.loads(compact_dashboard_evidence(result.model_dump(mode='json'))),'analysis_id':result.evidence_id}
        if trace.retrieval_status=='MISS' and not state.tool_results:
            state.final_response='No sufficiently matching evidence was found. Add relevant source material or clarify the question.'
            return self.checkpoint(state,'COMPLETED','retrieval_miss')
        return self.checkpoint(state,'RETRIEVING','retrieval_completed',trace.search_details)

    @staticmethod
    def selected_evidence(state):
        return [r for r in state.retrieval_trace.results if r.chunk.chunk_id in state.retrieval_trace.final_chunk_ids]

    def generate_draft(self,state):
        policy=Policy(**state.policy)
        if state.iteration>=policy.maximum_agent_iterations:
            raise Conflict('Maximum correction attempts reached')
        state.iteration+=1
        comment=state.reviews[-1]['comment'] if state.reviews else None
        if state.artifacts and state.artifacts[-1].evaluation.decision!='PASS':
            comment='Address evaluation issues: '+ '; '.join(state.artifacts[-1].evaluation.issues)
        body=AgentInput(query=state.request.question,evidence=self.selected_evidence(state),tool_results=state.tool_results,
            revision_comment=comment,previous_content=state.artifacts[-1].content if state.artifacts else None)
        review_required=bool(state.analysis.requires_hitl or state.reviews or state.retrieval_trace.retrieval_status=='WEAK_HIT')
        for name in [state.routing.selected_agent,*state.routing.secondary_agents]:
            state.agent_outputs.append(AGENTS[name](self.llm,policy).run(body,review_required))
        return self.checkpoint(state,'GENERATING','draft_generated',{'iteration':state.iteration,'model_call':getattr(self.llm,'last_call',{'purpose':'test-double'})})

    def evaluate_draft(self,state):
        policy=Policy(**state.policy)
        outputs=state.agent_outputs[-(1+len(state.routing.secondary_agents)):]
        content='\n\n'.join(output.answer for output in outputs)
        citations=list(dict.fromkeys(c for output in outputs for c in output.evidence))
        evaluation=EvaluationService(self.llm,policy).evaluate(state.request.question,content,self.selected_evidence(state),citations,state.tool_results)
        version=len(state.artifacts)+1
        human=any(output.requires_human_review for output in outputs)
        state.artifacts.append(Artifact(artifact_id=str(uuid.uuid4()),workflow_id=state.workflow_id,version=version,
            previous_version=version-1 if version>1 else None,agent='+'.join(o.agent_name for o in outputs),content=content,
            evidence=citations,limitations=list(dict.fromkeys(l for o in outputs for l in o.limitations)),
            risk_level=state.analysis.risk_level,review_required=human,review_status='PENDING' if human else 'NOT_REQUIRED',evaluation=evaluation))
        status='AWAITING_HUMAN_REVIEW' if human else 'EVALUATING'
        if evaluation.decision!='PASS':
            status='REVISION_REQUIRED' if state.iteration<policy.maximum_agent_iterations else 'FAILED'
            if status=='FAILED':
                state.error='Evaluation did not pass within the correction limit; no final output released.'
        return self.checkpoint(state,status,'evaluated',{'score':evaluation.overall_score,'decision':evaluation.decision})

    def finalize(self,state):
        artifact=state.artifacts[-1]
        if artifact.evaluation.decision!='PASS':
            raise Conflict('Evaluation has not passed')
        if artifact.review_required and (state.status!='APPROVED' or artifact.review_status!='APPROVED'):
            raise Conflict('Mandatory human approval is pending')
        if state.status not in ('APPROVED','EVALUATING'):
            raise Conflict('Invalid finalization state')
        state.final_response=state.reviews[-1]['modified_output'] if state.reviews and state.reviews[-1]['decision']=='MODIFY' else artifact.content
        return self.checkpoint(state,'COMPLETED','finalized',{'artifact_version':artifact.version})

    def review(self,identifier,decision,body,principal):
        if principal.role not in ('reviewer','admin'):
            raise PermissionError('Reviewer role required')
        with connection() as current:
            state=self.repository.get(identifier,current,lock=True)
            existing=current.execute('SELECT decision,rationale,modified_output,reviewer_id,artifact_version,workflow_revision FROM review_decisions WHERE workflow_id=%s AND idempotency_key=%s',(identifier,body.idempotency_key)).fetchone()
            if existing:
                if (existing['decision'],existing['rationale'],existing['modified_output'],existing['reviewer_id'],existing['artifact_version'],existing['workflow_revision'])!=(decision,body.comment,body.modified_output,principal.user_id,body.artifact_version,body.workflow_revision):
                    raise Conflict('Idempotency key was already used for a different decision')
                return state
            if state.status!='AWAITING_HUMAN_REVIEW' or state.revision!=body.workflow_revision:
                raise Conflict('Workflow changed; reload before reviewing')
            artifact=state.artifacts[-1]
            if artifact.version!=body.artifact_version:
                raise Conflict('Artifact changed; review the current version')
            if decision not in ('APPROVE','MODIFY','REJECT'):
                raise ValueError('Unknown review decision')
            if decision=='MODIFY':
                self.validate_modification(state,body.modified_output)
            elif body.modified_output is not None:
                raise ValueError('Only MODIFY accepts replacement text')
            review_id=str(uuid.uuid4())
            current.execute('''INSERT INTO review_decisions(id,workflow_id,reviewer_id,artifact_version,workflow_revision,
                decision,rationale,original_output,modified_output,idempotency_key) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                (review_id,identifier,principal.user_id,artifact.version,state.revision,decision,body.comment,artifact.content,body.modified_output,body.idempotency_key))
            state.reviews.append({'review_id':review_id,'reviewer':principal.name,'reviewer_id':principal.user_id,
                'decision':decision,'comment':body.comment,'timestamp':now(),'artifact_version':artifact.version,
                'original_output':artifact.content,'modified_output':body.modified_output})
            if decision=='REJECT':
                state.status='REVISION_REQUIRED' if state.iteration<state.policy['maximum_agent_iterations'] else 'FAILED'
                artifact.review_status='REJECTED'
            else:
                state.status='APPROVED'
                artifact.review_status='APPROVED'
            state=self.repository.save(state,'human_decision',{'review_id':review_id,'decision':decision},current)
            enqueue(current,state.user_id,identifier,{'review_id':review_id},'resume:'+review_id)
        return state

    def validate_modification(self,state,content):
        if not content or not content.strip():
            raise ValueError('A replacement assessment is required')
        support=' '.join(r.chunk.chunk_text for r in self.selected_evidence(state))+json.dumps(state.tool_results)
        numbers=lambda s:set(re.findall(r'(?<!\w)\d+(?:\.\d+)?',s.replace(',','')))
        if not numbers(content).issubset(numbers(support)):
            raise ValueError('Modified assessment contains unsupported numbers')
        prohibited=('caused patient harm','fda approved this facility','legally compliant','guaranteed compliance')
        if any(term in content.lower() for term in prohibited):
            raise ValueError('Modified assessment makes a prohibited unsupported conclusion')

    def run(self,identifier,decision=None):
        import psycopg
        from psycopg.rows import dict_row
        from sqlalchemy.engine import make_url
        from langgraph.checkpoint.postgres import PostgresSaver
        from langgraph.types import Command
        from .graph import build_graph
        url=make_url(database_url()).set(drivername='postgresql').render_as_string(hide_password=False)
        with psycopg.connect(url,autocommit=True,row_factory=dict_row) as current:
            current.execute('SELECT pg_advisory_lock(hashtextextended(%s,0))',('workflow:'+identifier,))
            try:
                graph=build_graph(self,PostgresSaver(current))
                config={'configurable':{'thread_id':identifier},'recursion_limit':40}
                snapshot=graph.get_state(config)
                if decision:
                    if not snapshot.next:
                        return self.repository.get(identifier)
                    value=Command(resume=decision)
                elif snapshot.values:
                    value=None
                else:
                    value={'workflow':self.repository.get(identifier).model_dump(mode='json'),'decision':None}
                graph.invoke(value,config)
            finally:
                current.execute('SELECT pg_advisory_unlock(hashtextextended(%s,0))',('workflow:'+identifier,))
        return self.repository.get(identifier)
