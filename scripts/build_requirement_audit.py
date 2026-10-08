"""Build an evidence-linked audit and conservative static function map."""
import ast, hashlib, html, json, re
from collections import defaultdict
from pathlib import Path
from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT.parents[1] / 'outputs'
manifest = json.loads((OUT/'RegInsight-Code-Manifest.json').read_text(encoding='utf-8'))
frontend = json.loads((OUT/'RegInsight-Frontend-Symbols.json').read_text(encoding='utf-8'))
files = {f['path']: f for f in manifest['files']}
sources = {p: (ROOT/p).read_text(encoding='utf-8-sig') for p in files}
maps = {}
E = html.escape
def expr(n): return ast.unparse(n) if n is not None else 'None'
def source_link(p, line=1):
    return 'RegInsight-Code-Atlas.html#f'+hashlib.sha256(p.encode()).hexdigest()[:12]+(f'-L{line}' if files[p]['lines'] else '')
def local_module(name):
    stem = name.replace('.', '/')
    return next((p for p in (stem+'.py', stem+'/__init__.py') if p in files), None)
def js_module(p, name):
    if not name.startswith('.'): return None
    base = (ROOT/p).parent/name
    for candidate in [base]+[Path(str(base)+ext) for ext in ('.js','.jsx')]:
        rel = candidate.resolve().relative_to(ROOT).as_posix()
        if rel in files: return rel

class Visitor(ast.NodeVisitor):
    def __init__(self, path):
        self.path=path; self.stack=[]; self.symbols=[]; self.calls=[]; self.bindings={}
    def symbol(self, node):
        name='.'.join([s['leaf'] for s in self.stack]+[node.name])
        s=dict(id=f'{self.path}#{name}@{node.lineno}',name=name,leaf=node.name,
               kind=type(node).__name__,start=node.lineno,end=node.end_lineno,
               params=expr(node.args) if hasattr(node,'args') else ', '.join(map(expr,node.bases)),
               doc=ast.get_docstring(node) or '',returns=[],conditions=[],raises=[])
        self.symbols.append(s)
        # Decorators execute in enclosing scope, not the function body.
        for d in node.decorator_list: self.visit(d)
        self.stack.append(s)
        for n in node.body: self.visit(n)
        self.stack.pop()
    visit_FunctionDef=symbol
    visit_AsyncFunctionDef=symbol
    visit_ClassDef=symbol
    def visit_Call(self,n):
        self.calls.append(dict(owner=self.stack[-1]['id'] if self.stack else '<module>',line=n.lineno,expression=expr(n.func),kind='call'))
        self.generic_visit(n)
    def record(self,n,key,value):
        if self.stack: self.stack[-1][key].append(value[:400])
        self.generic_visit(n)
    def visit_Return(self,n): self.record(n,'returns',expr(n.value))
    def visit_If(self,n): self.record(n,'conditions',expr(n.test))
    def visit_Raise(self,n): self.record(n,'raises',expr(n.exc))
    def visit_Import(self,n):
        for a in n.names:
            self.bindings[a.asname or a.name.split('.')[0]]=(a.name if a.asname else a.name.split('.')[0], '')
    def visit_ImportFrom(self,n):
        base=n.module or ''
        if n.level:
            parts=self.path.split('/')[:-1]
            base='.'.join(parts[:len(parts)-n.level+1]+([base] if base else []))
        for a in n.names: self.bindings[a.asname or a.name]=(base,a.name)

for p,f in files.items():
    assert hashlib.sha256(sources[p].encode()).hexdigest()==f['sha256'], f'Snapshot changed: {p}'
    if p.endswith('.py'):
        v=Visitor(p); v.visit(ast.parse(sources[p])); maps[p]=dict(symbols=v.symbols,calls=v.calls,bindings=v.bindings)
    else: maps[p]=frontend.get(p,dict(symbols=[],calls=[],imports=[]))
    for s in maps[p]['symbols']:
        s['file']=p
        assert 1 <= s['start'] <= s['end'] <= f['lines'], (p,s)

symbols={s['id']:s for m in maps.values() for s in m['symbols']}
by_name={(p,s['name']):s['id'] for p,m in maps.items() for s in m['symbols']}
incoming=defaultdict(list)
def resolve(p,c):
    expression=c['expression']; owner=symbols.get(c['owner']); bits=expression.split('.')
    if not all(re.fullmatch(r'[A-Za-z_$][\w$]*',b) for b in bits): return None
    # Only explicit lexical names, self methods, and explicit imports are resolved.
    if len(bits)==1:
        scope=owner['name'].split('.') if owner else []
        for i in range(len(scope),-1,-1):
            found=by_name.get((p,'.'.join(scope[:i]+bits)))
            if found: return found
    if bits[0]=='self' and owner:
        return by_name.get((p,'.'.join(owner['name'].split('.')[:-1]+bits[1:])))
    if p.endswith('.py'):
        binding=maps[p]['bindings'].get(bits[0])
        if binding:
            module,member=binding
            if member and local_module(module+'.'+member): module,member=module+'.'+member,''
            tail='.'.join(([member] if member else [])+bits[1:])
            return by_name.get((local_module(module),tail))
        # Fully qualified module names imported without an alias.
        for cut in range(len(bits)-1,0,-1):
            if bits[0] in maps[p]['bindings']:
                found=by_name.get((local_module('.'.join(bits[:cut])),'.'.join(bits[cut:])))
                if found: return found
    else:
        for imp in maps[p].get('imports',[]):
            target=js_module(p,imp['module'])
            if not target: continue
            for binding in imp['bindings']:
                if binding['local']!=bits[0]: continue
                name=binding['imported']
                if name=='default':
                    match=re.search(r'export\s+default\s+(?:async\s+)?(?:function\s+)?(\w+)',sources[target])
                    name=match[1] if match else ''
                return by_name.get((target,'.'.join(([name] if name!='*' else [])+bits[1:])))
    return None
for p,m in maps.items():
    for c in m['calls']:
        c['target']=resolve(p,c)
        if c['target']: incoming[c['target']].append(dict(file=p,**c))

style='body{font:17px/1.6 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#182d40;background:#f7fafc}a{color:#075d96}h1,h2,h3{line-height:1.25}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd8e1;padding:10px;text-align:left;vertical-align:top}pre,code{font-family:Consolas,monospace;overflow-wrap:anywhere}pre{white-space:pre-wrap;background:#eaf0f5;padding:16px}section{margin:24px 0;padding:20px;background:white;border:1px solid #d4dfe7;border-radius:12px}details{border-top:1px solid #d4dfe7;padding:12px 0}summary{cursor:pointer;font-weight:700}input{font:inherit;padding:12px;width:90%;margin:16px 0}.muted{color:#506375}.toolbar{position:sticky;top:0;background:#f7fafc;padding:8px;z-index:1}li{margin-bottom:5px}'
def link(p,line,label): return f'<a href="{source_link(p,line)}">{E(label)}</a>'
def anchor(s): return 's'+hashlib.sha256(s['id'].encode()).hexdigest()[:16]
def symbol_link(s): return f'<a href="#{anchor(s)}">{E(s["file"]+" : "+s["name"])}</a>'
reverse=defaultdict(list)
for p,f in files.items():
    for dep in f['imports']: reverse[dep].append(p)
parts=['<!doctype html><meta charset="utf-8"><title>RegInsight function connections</title><style>'+style+'</style>',
       '<h1>RegInsight: files, functions and connections</h1><p>Read the <a href="RegInsight-Requirement-Audit.html">requirement audit</a> and <a href="RegInsight-Project-Walkthrough.html">page-by-page explanation</a> first.</p>',
       f'<p>{len(files)} files; {len(symbols)} functions, classes and JavaScript callbacks. Exact source ranges are clickable. Return expressions and guards are extracted code, not a claim that every branch executes. Calls are a conservative static map, not a runtime trace. No static caller does not mean unused: routes, event callbacks and dependency injection are invoked indirectly. Python lambdas remain visible in the numbered source rather than separate named entries.</p>',
       '<div class="toolbar"><label>Search files or functions <input id="search" placeholder="summaries, run_batch, Experience, ingestion…"></label></div>']
for p,f in files.items():
    m=maps[p]; parts.append(f'<section class="file"><h2>{E(p)}</h2><p>{link(p,1,"Source: lines 1–"+str(f["lines"])) if f["lines"] else "Empty package marker; no executable lines."}</p>')
    for label,paths in [('Imports',f['imports']),('Imported by',reverse[p])]:
        parts.append('<p><b>'+label+': </b>'+(', '.join(link(q,1,q) for q in paths) or 'No indexed local modules.')+'</p>')
    if not m['symbols']: parts.append('<p>No indexed function declarations. Inspect the source for module-level statements, configuration, styles or startup commands.</p>')
    for s in m['symbols']:
        parts.append(f'<details id="{anchor(s)}"><summary>{E(s["name"])} · {E(s["kind"])} · lines {s["start"]}–{s["end"]}</summary>')
        parts.append('<p>'+link(p,s['start'],'Open definition')+' · '+link(p,s['end'],'Open end of implementation')+'</p><p><b>Parameters / class bases:</b> <code>'+E(s['params'] or '(none)')+'</code></p>')
        if s['doc']: parts.append('<p>'+E(s['doc'])+'</p>')
        for label,key in [('Return expressions','returns'),('Branch conditions','conditions'),('Raised errors','raises')]:
            vals=list(dict.fromkeys(s[key]))
            parts.append('<p><b>'+label+':</b></p><pre>'+E('\n'.join(vals) if vals else 'None explicitly extracted; inspect the source for implicit results and side effects.')+'</pre>')
        parts.append('<p><b>Outgoing calls / component renders:</b></p><ul>')
        cs=[c for c in m['calls'] if c['owner']==s['id']]
        for c in cs:
            dest=symbol_link(symbols[c['target']]) if c['target'] else 'External, built-in, or dynamically bound; target not statically resolved.'
            parts.append('<li>'+link(p,c['line'],f'L{c["line"]}')+' <code>'+E(c['expression'])+'</code> → '+dest+'</li>')
        if not cs: parts.append('<li>No calls extracted from this body.</li>')
        parts.append('</ul><p><b>Incoming static references:</b></p><ul>')
        for c in incoming[s['id']]:
            owner=symbols.get(c['owner']); label=c['file']+' : '+(owner['name'] if owner else 'module initialization')+f' L{c["line"]}'
            parts.append('<li>'+link(c['file'],c['line'],label)+'</li>')
        if not incoming[s['id']]: parts.append('<li>No static caller found; consult API routes, callback registration and module imports.</li>')
        parts.append('</ul></details>')
    module_calls=[c for c in m['calls'] if c['owner']=='<module>']
    if module_calls:
        parts.append('<details><summary>Module initialization / registration calls</summary><ul>')
        for c in module_calls: parts.append('<li>'+link(p,c['line'],f'L{c["line"]}')+' <code>'+E(c['expression'])+'</code></li>')
        parts.append('</ul></details>')
    parts.append('</section>')
parts.append('''<script>document.querySelector('#search').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('.file').forEach(f=>{f.hidden=!f.textContent.toLowerCase().includes(q)})});function reveal(){const el=document.getElementById(location.hash.slice(1));if(el){el.closest('.file').hidden=false;el.open=true;el.scrollIntoView()}}addEventListener('hashchange',reveal);reveal();</script>''')
(OUT/'RegInsight-Function-Connections.html').write_text('\n'.join(parts),encoding='utf-8')
(OUT/'RegInsight-Function-Connections.json').write_text(json.dumps(dict(source_root=str(ROOT),files=maps),indent=2),encoding='utf-8')
template=(ROOT/'docs/image-requirements-audit.template.md').read_text(encoding='utf-8')
references=[]
def ref(match, portable):
    value=match[1]; p,_,name=value.partition('#'); assert p in files,p
    line=1
    if name:
        candidates=[s for s in maps[p]['symbols'] if s['name']==name]
        if not candidates: candidates=[s for s in maps[p]['symbols'] if s['leaf']==name]
        assert len(candidates)==1,(p,name,len(candidates))
        line=candidates[0]['start']
    references.append((p,line))
    url=source_link(p,line) if portable else (ROOT/p).as_posix()+f':{line}'
    return f'[{value} · L{line}]({url})'
md=re.sub(r'\[\[([^\]]+)\]\]',lambda m:ref(m,False),template)
portable=re.sub(r'\[\[([^\]]+)\]\]',lambda m:ref(m,True),template)
portable+='\n\n[Open the per-file function map](RegInsight-Function-Connections.html) · [Open the page-by-page walkthrough](RegInsight-Project-Walkthrough.html)\n'
(OUT/'RegInsight-Requirement-Audit.md').write_text(md,encoding='utf-8')
(OUT/'RegInsight-Requirement-Audit.html').write_text('<!doctype html><meta charset="utf-8"><title>RegInsight requirement audit</title><style>'+style+'</style>'+MarkdownIt().render(portable),encoding='utf-8')
print(json.dumps(dict(files=len(files),symbols=len(symbols),calls=sum(len(m['calls']) for m in maps.values()),resolved_calls=sum(len(v) for v in incoming.values()),audit_references=len(references)//2)))
