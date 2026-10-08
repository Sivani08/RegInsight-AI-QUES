from .chunking import chunk_document
from backend.workflows.schemas import RetrievalTrace
import os
import httpx
import psycopg

class RetrievalService:
    def __init__(self, repository, policy):
        self.repository=repository;self.embedding=repository.embedding;self.policy=policy

    def ingest(self,document):
        return self.repository.upsert_document(chunk_document(document,self.policy,self.embedding))

    def search(self,query,query_id,filters=None):
        p=self.policy;filters=filters or {}
        mode=os.getenv('RETRIEVAL_MODE','hybrid')
        fallback=None
        try:
            vector=None if mode=='keyword' else self.embedding.embed_query(query)
            results=self.repository.search(vector,filters,p.retrieval_candidate_limit,query=query,mode=mode)
        except (httpx.HTTPError, psycopg.errors.DataException) as error:
            mode='keyword'
            fallback=type(error).__name__
            results=self.repository.search(None,filters,p.retrieval_candidate_limit,query=query,mode=mode)
        best=max((result.similarity_score for result in results),default=0)
        status='STRONG_HIT' if best>=p.strong_hit_threshold else 'WEAK_HIT' if best>=p.weak_hit_threshold else 'MISS'
        selected=[r.chunk.chunk_id for r in results if r.similarity_score>=p.weak_hit_threshold][:p.retrieval_top_k]
        if mode=='keyword':
            selected=[r.chunk.chunk_id for r in results[:p.retrieval_top_k]]
            status='WEAK_HIT' if selected else 'MISS'
        details={**self.repository.last_trace,'fallback_reason':fallback}
        return RetrievalTrace(query_id=query_id,query=query,embedding_model=self.embedding.model,
            embedding_version=self.embedding.version,embedding_dimensions=self.embedding.dimensions,filters=filters,
            search_details=details,top_k=p.retrieval_top_k,thresholds={'strong':p.strong_hit_threshold,'weak':p.weak_hit_threshold},
            results=results,final_chunk_ids=selected,retrieval_status=status)

    def seed_references(self,root):
        import json
        total=0
        for doc in json.loads((root/'config/chat_knowledge.json').read_text(encoding='utf-8')):
            total+=self.ingest({'document_id':doc['id'],'name':doc['title'],'text':doc['text'],
                'source_type':'project_reference','domain':'Regulatory','metadata':{'locator':doc['locator'],
                'authority':'project_reference_not_regulatory_authority',**({'url':doc['url']} if doc.get('url') else {})}})
        return total
