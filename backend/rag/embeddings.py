"""Local Ollama semantic embeddings, with model identity verified at startup."""
import math
import os
from urllib.parse import urlparse
import httpx


class EmbeddingService:
    def __init__(self, dimensions=None, model=None):
        self.model = model or os.getenv('EMBEDDING_MODEL', 'nomic-embed-text:latest')
        self.base_url = os.getenv('OLLAMA_BASE_URL', 'http://127.0.0.1:11434').rstrip('/')
        address = urlparse(self.base_url)
        allowed=os.getenv('OLLAMA_ALLOWED_HOSTS','127.0.0.1,localhost,::1').split(',')
        if address.scheme!='http' or address.hostname not in allowed or address.username or address.password or address.path or address.query:
            raise ValueError('Invalid local model endpoint')
        self.client = httpx.Client(base_url=self.base_url, timeout=60, trust_env=False)
        response = self.client.get('/api/tags')
        response.raise_for_status()
        selected = next((m for m in response.json()['models'] if m['name'] == self.model), None)
        if not selected:
            raise RuntimeError('Install the configured local embedding model before indexing')
        self.version = selected['digest']
        probe = self.embed_documents(['Regulatory evidence dimension probe'])[0]
        self.dimensions = len(probe)
        if dimensions is not None and dimensions != self.dimensions:
            raise ValueError('Configured dimension does not match the actual embedding model')

    def embed_documents(self, texts):
        if not texts:
            return []
        response = self.client.post('/api/embed', json={'model': self.model, 'input': texts, 'truncate': False})
        response.raise_for_status()
        vectors = response.json()['embeddings']
        if len(vectors) != len(texts):
            raise ValueError('Embedding provider returned the wrong batch size')
        for vector in vectors:
            if not vector or not all(math.isfinite(x) for x in vector) or not any(vector):
                raise ValueError('Embedding provider returned an invalid vector')
            if hasattr(self, 'dimensions') and len(vector) != self.dimensions:
                raise ValueError('Embedding dimension changed')
        return vectors

    def embed(self, text):
        return self.embed_documents([text])[0]

    def embed_query(self, query):
        return self.embed(query)
