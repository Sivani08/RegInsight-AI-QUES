import hashlib, re
from .embeddings import EmbeddingService
from backend.workflows.schemas import Chunk

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
            index=len(result)
            identity=f'{document_id}\0{index}\0{part}\0{embedding.model}\0{embedding.version}\0{embedding.dimensions}'
            result.append(Chunk(chunk_id='CHK-'+hashlib.sha256(identity.encode()).hexdigest()[:32],
                document_id=document_id,document_name=document['name'],source_type=document['source_type'],
                domain=document.get('domain','Quality'),section=document.get('section'),page_number=document.get('page_number'),
                chunk_index=index,chunk_text=part,token_count=end-start,metadata=metadata,
                embedding_model=embedding.model,embedding_version=embedding.version))
            if end==len(spans): break
            start=end-policy.chunk_overlap
    return result
