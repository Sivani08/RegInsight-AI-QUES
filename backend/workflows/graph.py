"""Durable stage graph; deterministic services remain ordinary Python functions."""
from typing import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
from .schemas import WorkflowState


class GraphState(TypedDict):
    workflow: dict
    decision: dict | None


def build_graph(service, checkpointer):
    def stage(function):
        def invoke(value: GraphState):
            state=WorkflowState.model_validate(value['workflow'])
            return {'workflow':function(state).model_dump(mode='json')}
        return invoke

    def review(value: GraphState):
        state=WorkflowState.model_validate(value['workflow'])
        decision=interrupt({'workflow_id':state.workflow_id,'artifact_version':state.artifacts[-1].version,'revision':state.revision})
        return {'decision':decision}

    def apply_review(value: GraphState):
        state=service.repository.get(value['workflow']['workflow_id'])
        decision=value.get('decision') or {}
        if not state.reviews or state.reviews[-1].get('review_id')!=decision.get('review_id'):
            raise ValueError('Resume requires a persisted review decision')
        return {'workflow':state.model_dump(mode='json')}

    graph=StateGraph(GraphState)
    for name, function in [('route',service.determine_route),('retrieve',service.retrieve_evidence),
        ('generate',service.generate_draft),('evaluate',service.evaluate_draft),('finalize',service.finalize)]:
        graph.add_node(name,stage(function))
    graph.add_node('review',review)
    graph.add_node('apply_review',apply_review)
    graph.add_edge(START,'route')
    graph.add_conditional_edges('route',lambda s: 'stop' if s['workflow']['status']=='COMPLETED' else 'retrieve',{'stop':END,'retrieve':'retrieve'})
    graph.add_conditional_edges('retrieve',lambda s:'stop' if s['workflow']['status']=='COMPLETED' else 'generate',{'stop':END,'generate':'generate'})
    graph.add_edge('generate','evaluate')
    graph.add_conditional_edges('evaluate',lambda s:{'FAILED':'stop','REVISION_REQUIRED':'generate','AWAITING_HUMAN_REVIEW':'review'}.get(s['workflow']['status'],'finalize'),
        {'stop':END,'generate':'generate','review':'review','finalize':'finalize'})
    graph.add_edge('review','apply_review')
    graph.add_conditional_edges('apply_review',lambda s:'finalize' if s['workflow']['status']=='APPROVED' else 'stop' if s['workflow']['status']=='FAILED' else 'generate',
        {'finalize':'finalize','generate':'generate','stop':END})
    graph.add_edge('finalize',END)
    return graph.compile(checkpointer=checkpointer)
