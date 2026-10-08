"""Wire the existing domain services into the durable workflow runtime."""
from .policy import load_policy
from .repository import WorkflowRepository
from .service import WorkflowService
from backend.rag.embeddings import EmbeddingService
from backend.rag.repository import VectorRepository
from backend.rag.service import RetrievalService
from backend.libraries.structured_llm import StructuredLLM
from backend.services.dashboard_insights import DashboardInsights


def create_workflows(inspection_service):
    policy=load_policy()
    embedding=EmbeddingService(policy.embedding_dimensions,policy.embedding_model)
    policy.embedding_dimensions=embedding.dimensions
    retrieval=RetrievalService(VectorRepository(embedding=embedding,max_chunks=policy.max_index_chunks),policy)
    return WorkflowService(WorkflowRepository(),retrieval,StructuredLLM(policy.llm_timeout_seconds),
                           policy,DashboardInsights(inspection_service))
