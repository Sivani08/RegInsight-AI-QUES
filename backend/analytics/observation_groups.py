"""Cached local vectors and bounded candidate search; no remote embeddings."""
import os,re,math,hashlib,json
from collections import Counter,defaultdict,deque
from pathlib import Path
from backend.analytics.intelligence_taxonomy import VERSION

class Grouper:
    def __init__(self,threshold=None,model_path=None):
        self.threshold=float(os.getenv('OBSERVATION_SIMILARITY_THRESHOLD','0.78')) if threshold is None else threshold
        if not 0<self.threshold<=1:raise ValueError('Similarity threshold must be in (0,1]')
        self.model=None;self.method='lexical_cosine';self.reps={};self.inverted=defaultdict(lambda:deque(maxlen=300))
        self.embedding_model='local-taxonomy-lexical';self.embedding_version='3:'+VERSION
        self.pending={};self.cache_hits=0;self.comparisons=0;self.planes=None
        model_path=model_path or os.getenv('OBSERVATION_EMBEDDING_MODEL_PATH')
        if model_path:
            from sentence_transformers import SentenceTransformer
            if not Path(model_path).is_dir():raise ValueError('Embedding model must be preinstalled locally')
            fingerprint=hashlib.sha256()
            for file in sorted(p for p in Path(model_path).rglob('*') if p.is_file()):
                fingerprint.update(str(file.relative_to(model_path)).encode())
                with file.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):fingerprint.update(chunk)
            self.embedding_model=str(Path(model_path).resolve());self.embedding_version='3:'+fingerprint.hexdigest()
            self.model=SentenceTransformer(model_path,device='cpu',local_files_only=True)
            self.method='sentence_transformer_lsh_cosine'

    def vector(self,text):
        if self.model is not None:return self.model.encode(text,normalize_embeddings=True)
        low=text.lower()
        tokens=re.findall(r'[a-z0-9]{3,}',low)
        aliases={'entries':'records','record':'records','laboratories':'laboratory'}
        stop={'the','and','were','was','for','with','that','not','are','your','specifically','failure','maintain','documented'}
        c=Counter(aliases.get(t,t) for t in tokens if t not in stop)
        # Domain signal only, not a claim of regulatory equivalence.
        if any(t in low for t in ('contemporaneous','retrospectiv','backdat','after testing')):
            c['record_timing']=5
        norm=math.sqrt(sum(v*v for v in c.values())) or 1
        return {k:v/norm for k,v in c.items()}

    def prepare(self,rows,connection):
        """Batch inference only for uncached vectors; bounded memory per ETL batch."""
        self.pending={};missing=[]
        for row in rows:
            h=row['hash'];cached=connection.execute('SELECT payload FROM embeddings WHERE hash=%s AND model=%s AND version=%s',(h,self.embedding_model,self.embedding_version)).fetchone()
            if cached:
                try:
                    v=json.loads(cached[0])
                    if self.model is not None:
                        import numpy as np
                        v=np.asarray(v,dtype=float)
                        if v.ndim!=1 or not len(v) or not np.isfinite(v).all():raise ValueError('Invalid vector')
                    elif not isinstance(v,dict) or any(not isinstance(x,(int,float)) or not math.isfinite(x) for x in v.values()):raise ValueError('Invalid vector')
                    self.pending[h]=v;self.cache_hits+=1;continue
                except (ValueError,TypeError):pass
            missing.append(row)
        vectors=self.model.encode([r['text'] for r in missing],batch_size=64,normalize_embeddings=True) if self.model is not None and missing else [self.vector(r['text']) for r in missing]
        for row,v in zip(missing,vectors):
            self.pending[row['hash']]=v
            connection.execute('INSERT INTO texts(hash,text) VALUES (%s,%s) ON CONFLICT(hash) DO NOTHING',(row['hash'],row['text']))
            connection.execute('INSERT INTO embeddings VALUES (%s,%s,%s,%s) ON CONFLICT (hash,model,version) DO UPDATE SET payload=EXCLUDED.payload',(row['hash'],self.embedding_model,self.embedding_version,json.dumps(v.tolist() if self.model is not None else v)))

    def signatures(self,v):
        import numpy as np
        if self.planes is None:self.planes=np.random.default_rng(42).normal(size=(12,12,len(v)))
        return [sum(int(bit)<<i for i,bit in enumerate(bits)) for bits in (self.planes@v>=0)]

    def assign(self,h,text,theme):
        v=self.pending[h] if h in self.pending else self.vector(text)
        best=None;score=0.;candidates=set()
        if self.model is not None:
            keys=[(theme,table,bits) for table,bits in enumerate(self.signatures(v))]
            for key in keys:
                candidates.update(self.inverted[key])
                for bit in range(12):candidates.update(self.inverted[(theme,key[1],key[2]^(1<<bit))])
        else:
            keys=[(theme,t) for t in v]
            for token in sorted(v,key=lambda t:(len(self.inverted[(theme,t)]),t))[:8]:candidates.update(self.inverted[(theme,token)])
        for key in sorted(candidates)[:300]:
            old=self.reps[key][1];self.comparisons+=1
            sim=float(v@old) if self.model is not None else sum(weight*old.get(t,0) for t,weight in v.items())
            if sim>score:best=key;score=sim
        if best is not None and score>=self.threshold:return best,min(1.,score),self.method
        group='GRP-'+hashlib.sha256(json.dumps([self.embedding_model,self.embedding_version,self.threshold,theme,h]).encode()).hexdigest()[:20]
        self.reps[group]=(theme,v)
        for key in keys:self.inverted[key].append(group)
        return group,1.,self.method
