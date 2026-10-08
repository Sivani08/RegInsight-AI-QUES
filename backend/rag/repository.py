"""Exact pgvector and PostgreSQL full-text retrieval over the same evidence rows."""
import hashlib
import json
import os
import time
from contextvars import ContextVar
from psycopg.types.json import Jsonb
from backend.database.postgres import connection
from backend.workflows.schemas import Chunk, RetrievedChunk

FILTERS = {'document_id', 'domain', 'dataset', 'source_type', 'company', 'site', 'year',
           'inspection_type', 'classification', 'severity', 'theme', 'source', 'observation_id'}
_retrieval_trace = ContextVar('retrieval_trace', default=None)


class VectorRepository:
    def __init__(self, path=None, embedding=None, max_chunks=25000):
        if embedding is None:
            raise ValueError('A semantic embedding provider is required')
        self.embedding = embedding
        self.max_chunks = max_chunks
        self.space = f'{embedding.model}:{embedding.version}:{embedding.dimensions}'
        with connection() as current:
            current.execute('''INSERT INTO embedding_metadata(space,model,version,dimensions)
                VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING''',
                (self.space, embedding.model, embedding.version, embedding.dimensions))

    @property
    def last_trace(self):
        return _retrieval_trace.get() or {}

    def upsert_document(self, chunks):
        if not chunks:
            return 0
        document_id = chunks[0].document_id
        if any(chunk.document_id != document_id for chunk in chunks):
            raise ValueError('Index one document per transaction')
        # Finish inference before replacing evidence, so provider failures preserve the old index.
        vectors = []
        for start in range(0, len(chunks), 32):
            vectors.extend(self.embedding.embed_documents([c.chunk_text for c in chunks[start:start+32]]))
        with connection() as current:
            current.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', ('retrieval-index',))
            count = current.execute('SELECT count(*) FROM retrieval_chunks WHERE space=%s AND document_id<>%s', (self.space, document_id)).fetchone()[0]
            if count + len(chunks) > self.max_chunks:
                raise ValueError('Configured corpus capacity exceeded')
            first = chunks[0]
            current.execute('''INSERT INTO retrieval_documents(id,source_name,metadata) VALUES (%s,%s,%s)
                ON CONFLICT(id) DO UPDATE SET source_name=EXCLUDED.source_name,metadata=EXCLUDED.metadata,updated_at=now()''',
                (document_id, document_id, Jsonb(first.metadata)))
            current.execute('DELETE FROM retrieval_chunks WHERE space=%s AND document_id=%s', (self.space, document_id))
            for chunk, vector in zip(chunks, vectors):
                metadata = {**chunk.metadata, 'document_id':document_id, 'domain':chunk.domain, 'source_type':chunk.source_type}
                current.execute('''INSERT INTO retrieval_chunks(space,chunk_id,document_id,text,payload,metadata,content_hash,chunking_version,embedding)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s::vector)''',
                    (self.space,chunk.chunk_id,document_id,chunk.chunk_text,Jsonb(chunk.model_dump(mode='json')),
                     Jsonb(metadata),hashlib.sha256(chunk.chunk_text.encode()).hexdigest(),'page-paragraph-v1',json.dumps(vector)))
        return len(chunks)

    def search(self, query_vector, filters, limit, query='', mode=None):
        mode = mode or os.getenv('RETRIEVAL_MODE', 'hybrid')
        if mode not in ('keyword','vector','hybrid') or not 1 <= limit <= 100:
            raise ValueError('Invalid retrieval mode or limit')
        if set(filters) - FILTERS:
            raise ValueError('Unsupported evidence filter')
        if mode != 'keyword' and (query_vector is None or len(query_vector) != self.embedding.dimensions):
            raise ValueError('Embedding dimension mismatch')
        started = time.monotonic()
        candidates = {}
        where = 'space=%s AND metadata @> %s'
        params = (self.space, Jsonb(filters))
        with connection() as current:
            if mode in ('vector','hybrid'):
                rows = current.execute('SELECT chunk_id,payload,1-(embedding <=> %s::vector) score FROM retrieval_chunks WHERE '+where+' ORDER BY embedding <=> %s::vector,chunk_id LIMIT %s',
                    (json.dumps(query_vector),*params,json.dumps(query_vector),limit*3)).fetchall()
                for rank,row in enumerate(rows,1):
                    candidates[row['chunk_id']] = {**row,'vector_rank':rank,'keyword_score':0.0,'keyword_rank':None}
            if mode in ('keyword','hybrid'):
                rows = current.execute("SELECT chunk_id,payload,ts_rank_cd(search_vector,websearch_to_tsquery('english',%s)) keyword_score FROM retrieval_chunks WHERE "+where+" AND search_vector @@ websearch_to_tsquery('english',%s) ORDER BY keyword_score DESC,chunk_id LIMIT %s",(query,*params,query,limit*3)).fetchall()
                for rank,row in enumerate(rows,1):
                    entry=candidates.setdefault(row['chunk_id'],{**row,'score':0.0,'vector_rank':None})
                    entry.update(keyword_score=float(row['keyword_score']),keyword_rank=rank)
        for entry in candidates.values():
            # Rank fusion avoids mixing unrelated lexical and cosine score scales.
            entry['final_score'] = sum(1/(60+entry[key]) for key in ('vector_rank','keyword_rank') if entry.get(key)) if mode=='hybrid' else float(entry['score'] if mode=='vector' else entry['keyword_score'])
        ranked=sorted(candidates.values(),key=lambda r:(-r['final_score'],r['chunk_id']))[:limit]
        _retrieval_trace.set({'mode':mode,'filters':filters,'candidate_count':len(candidates),'latency_ms':round((time.monotonic()-started)*1000,2),
            'candidates':[{k:v for k,v in entry.items() if k!='payload'} for entry in candidates.values()], 'selected_chunk_ids':[r['chunk_id'] for r in ranked]})
        return [RetrievedChunk(chunk=Chunk.model_validate(row['payload']),similarity_score=float(row['score']),rank=i+1) for i,row in enumerate(ranked)]

    def count(self):
        with connection() as current:
            return current.execute('SELECT count(*) FROM retrieval_chunks WHERE space=%s',(self.space,)).fetchone()[0]
