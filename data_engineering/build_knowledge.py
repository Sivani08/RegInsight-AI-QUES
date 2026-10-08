"""Build a local, source-addressable index of supplied reference documents."""
import hashlib,json,zipfile,re
from backend.database.postgres import connection
from pathlib import Path
import xml.etree.ElementTree as ET
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[1]
def build(root=ROOT):
    folder=root/'data/knowledge';folder.mkdir(parents=True,exist_ok=True)
    sources=[];chunks=[]
    for p in sorted((folder/'sources').glob('*')):
        if p.suffix.lower() not in ('.pdf','.pptx'):continue
        h=hashlib.sha256(p.read_bytes()).hexdigest();sid=h[:16]
        sources.append({'id':sid,'title':p.name,'sha256':h,'path':str(p.relative_to(root)),'authority':'supplied_reference_not_regulatory_authority','review_status':'reference_only'})
        if p.suffix.lower()=='.pdf':
            units=[('page '+str(i+1),page.extract_text() or '') for i,page in enumerate(PdfReader(p).pages)]
        else:
            with zipfile.ZipFile(p) as z:
                names=sorted((n for n in z.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n)),key=lambda n:int(re.search(r'(\d+)\.xml',n).group(1)))
                units=[('slide '+re.search(r'(\d+)\.xml',n).group(1),'\n'.join(e.text for e in ET.fromstring(z.read(n)).iter('{http://schemas.openxmlformats.org/drawingml/2006/main}t') if e.text)) for n in names]
        chunks.extend((sid,loc,text) for loc,text in units)
    with connection('knowledge') as c:
        c.execute('DELETE FROM chunks')
        c.execute('DELETE FROM sources')
        c.cursor().executemany('INSERT INTO sources VALUES (%s,%s)',[(s['id'],json.dumps(s)) for s in sources])
        c.cursor().executemany('INSERT INTO chunks(source_id,locator,text) VALUES (%s,%s,%s)',chunks)
    manifest={'sources':sources,'indexed_units':len(chunks),'policy':'References are searchable evidence, not automatically approved regulations. Dataset facts remain in source databases.'}
    (folder/'manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8');return manifest
if __name__=='__main__':print(json.dumps(build(),indent=2))
