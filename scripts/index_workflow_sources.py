"""Explicit source indexing; never silently embeds the entire inspection corpus."""
import argparse,json,sys,hashlib,zipfile,re
from pathlib import Path
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.workflows.policy import load_policy
from backend.rag.embeddings import EmbeddingService
from backend.rag.repository import VectorRepository
from backend.rag.service import RetrievalService

def documents(path):
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    common={'name':path.name,'domain':'Regulatory','metadata':{'source_file':str(path),
        'sha256':digest,'authority':'supplied_reference_not_regulatory_authority'}}
    if path.suffix.lower()=='.pdf':
        from pypdf import PdfReader
        for i,page in enumerate(PdfReader(path).pages,1):
            yield {**common,'document_id':digest+':page:'+str(i),'source_type':'pdf','page_number':i,'text':page.extract_text() or ''}
    elif path.suffix.lower()=='.pptx':
        with zipfile.ZipFile(path) as z:
            names=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
            for i,n in enumerate(names,1):
                text='\n'.join(e.text for e in ET.fromstring(z.read(n)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t') if e.text)
                yield {**common,'document_id':digest+':slide:'+str(i),'source_type':'pptx','section':'slide '+str(i),'text':text}
    elif path.suffix.lower() in ('.txt','.md'):
        yield {**common,'document_id':digest,'source_type':'text','text':path.read_text(encoding='utf-8')}
    else:raise ValueError('Supported source files: PDF, PPTX, TXT, MD')

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--database',default='PostgreSQL',choices=['PostgreSQL'])
    parser.add_argument('--source',action='append',default=[]);args=parser.parse_args()
    p=load_policy();e=EmbeddingService(p.embedding_dimensions,p.embedding_model)
    s=RetrievalService(VectorRepository(args.database,e,p.max_index_chunks),p)
    count=s.seed_references(ROOT)
    for name in args.source:
        path=Path(name).resolve()
        if path.stat().st_size>50*1024*1024:raise ValueError('Source file exceeds 50 MB')
        for d in documents(path):
            if d['text'].strip():count+=s.ingest(d)
    print(json.dumps({'indexed_chunks':count,'total_chunks':s.repository.count(),'database':args.database}))
if __name__=='__main__':main()
