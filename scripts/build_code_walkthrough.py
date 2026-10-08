"""Produce a local, reproducible source atlas and resolve guide line references.

No application database or secret configuration is opened by this documentation tool.
"""
import ast,hashlib,html,json,re
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT.parents[1]/'outputs'
SOURCE_DIRS=['backend','data_engineering','frontend/src','evaluation','tests']
RUNTIME_SCRIPTS=['prepare_workspace.py','prepare_retrieval.py','collect_evaluation.py','benchmark_retrieval.py','check_branding.py','browser_check.py']
SUFFIXES={'.py','.js','.jsx','.css','.yaml','.ps1','.cmd','.html','.txt'}
files=[]
for directory in SOURCE_DIRS:
    files.extend(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in SUFFIXES and not any(x in p.parts for x in ('__pycache__','fonts','assets')))
files.extend(ROOT/'scripts'/name for name in RUNTIME_SCRIPTS)
files.extend(ROOT/name for name in ['Start-RegInsight.ps1','Start-RegInsight.cmd','requirements-app.txt','requirements-eval.txt','frontend/index.html','frontend/vite.config.js','config/risk_weights.yaml','config/schema_mapping.yaml','config/alert_rules.yaml'])
files=sorted(set(p for p in files if p.exists()))
contents={p.relative_to(ROOT).as_posix():p.read_text(encoding='utf-8-sig') for p in files}
ids={path:'f'+hashlib.sha256(path.encode()).hexdigest()[:12] for path in contents}
symbols={};dependencies={};statements={};routes=[];calls={}

def expr(node):
    try:return ast.unparse(node)
    except Exception:return type(node).__name__

def py_target(module):
    stem=module.replace('.','/')
    return next((p for p in (stem+'.py',stem+'/__init__.py') if p in contents),None)

for path,source in contents.items():
    deps=set();syms=[];nodes={};call_refs=[]
    if path.endswith('.py'):
        tree=ast.parse(source,filename=path)
        prefixes={}
        for node in ast.walk(tree):
            if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and expr(node.value.func).endswith('APIRouter'):
                for target in node.targets:
                    if isinstance(target,ast.Name):prefixes[target.id]=next((k.value.value for k in node.value.keywords if k.arg=='prefix' and isinstance(k.value,ast.Constant)),'')
            if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef,ast.ClassDef)):
                syms.append({'name':node.name,'line':node.lineno,'end':node.end_lineno,'kind':type(node).__name__,'doc':ast.get_docstring(node) or ''})
                for dec in node.decorator_list:
                    if isinstance(dec,ast.Call) and isinstance(dec.func,ast.Attribute) and dec.func.attr in ('get','post','put','delete','patch') and dec.args and isinstance(dec.args[0],ast.Constant):
                        route=str(dec.args[0].value);prefix=prefixes.get(expr(dec.func.value),'')
                        routes.append({'method':dec.func.attr.upper(),'route':prefix+route,'file':path,'line':node.lineno,'handler':node.name})
            if isinstance(node,ast.stmt) and hasattr(node,'lineno'):
                nodes.setdefault(node.lineno,[]).append(node)
            if isinstance(node,ast.ImportFrom):
                base=node.module or ''
                if node.level:
                    package=path.split('/')[:-1]
                    package=package[:len(package)-node.level+1]
                    base='.'.join(package+([base] if base else []))
                for candidate in [base]+[base+'.'+a.name for a in node.names]:
                    target=py_target(candidate)
                    if target and target!=path:deps.add(target)
            if isinstance(node,ast.Import):
                for a in node.names:
                    target=py_target(a.name)
                    if target:deps.add(target)
            if isinstance(node,ast.Call):call_refs.append({'line':node.lineno,'expression':expr(node.func)})
    elif path.endswith(('.js','.jsx')):
        for match in re.finditer(r'\bfunction\s+(\w+)\s*\(',source):
            syms.append({'name':match[1],'line':source[:match.start()].count('\n')+1,'kind':'function','doc':''})
        for match in re.finditer(r'(?:\bfrom\s*|\bimport\s*\(?)[\'"]([^\'"]+)[\'"]',source):
            if match[1].startswith('.'):
                base=(ROOT/path).parent/match[1]
                for target in [base]+[Path(str(base)+ext) for ext in ('.js','.jsx','.css')]+[base/'index.js']:
                    resolved=target.resolve().relative_to(ROOT).as_posix()
                    if resolved in contents:deps.add(resolved);break
    symbols[path]=sorted(syms,key=lambda s:s['line']);dependencies[path]=sorted(deps);statements[path]=nodes;calls[path]=call_refs

def note(path,number,line):
    stripped=line.strip()
    if not stripped:return 'Blank line separating code blocks.'
    if stripped.startswith(('#','//','/*','*')):return 'Comment: explains intent or implementation constraints; not executed.'
    matches=statements[path].get(number,[])
    pieces=[]
    for n in matches[:3]:
        if isinstance(n,(ast.Import,ast.ImportFrom)):description='Imports names used by this module; project-local dependencies are linked above.'
        elif isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)):description=f'Defines {n.name}; body runs when called. '+(ast.get_docstring(n) or '')
        elif isinstance(n,ast.ClassDef):description=f'Defines {n.name}'+(' with base(s) '+', '.join(expr(b) for b in n.bases) if n.bases else '')+'.'
        elif isinstance(n,(ast.Assign,ast.AnnAssign,ast.AugAssign)):
            targets=n.targets if isinstance(n,ast.Assign) else [n.target]
            description='Assigns or updates '+', '.join(expr(t) for t in targets)+'. The right-hand expression supplies the value.'
        elif isinstance(n,ast.Return):description='Returns '+(expr(n.value) if n.value else 'without a value')+' to the caller.'
        elif isinstance(n,ast.If):description='Branches when '+expr(n.test)+' evaluates true.'
        elif isinstance(n,(ast.For,ast.AsyncFor)):description='Iterates '+expr(n.target)+' over '+expr(n.iter)+'.'
        elif isinstance(n,ast.While):description='Repeats while '+expr(n.test)+' is true.'
        elif isinstance(n,(ast.With,ast.AsyncWith)):description='Enters managed resource/context: '+', '.join(expr(i.context_expr) for i in n.items)+'. Cleanup runs on exit.'
        elif isinstance(n,ast.Raise):description='Raises '+expr(n.exc)+'; stops this normal execution path.'
        elif isinstance(n,ast.Try):description='Begins guarded execution; following except/finally blocks handle failure or cleanup.'
        elif isinstance(n,ast.Assert):description='Checks invariant '+expr(n.test)+'; raises AssertionError if it fails.'
        elif isinstance(n,ast.Expr) and isinstance(n.value,ast.Constant) and isinstance(n.value.value,str):description='Documentation string / standalone string expression.'
        elif isinstance(n,ast.Expr):description='Evaluates '+expr(n.value)+'.'
        elif isinstance(n,ast.Break):description='Leaves the nearest loop.'
        elif isinstance(n,ast.Continue):description='Moves to the next iteration of the nearest loop.'
        else:description=type(n).__name__+' statement; inspect the source expression.'
        pieces.append(description[:350])
    if pieces:return ' '.join(pieces)+(' Additional statements share this line.' if len(matches)>3 else '')
    if stripped.startswith('@'):return 'Decorator: registers or wraps the following function/class.'
    if path.endswith('.py'):
        enclosing=[n for group in statements[path].values() for n in group if n.lineno<number<=getattr(n,'end_lineno',n.lineno)]
        if enclosing:
            n=min(enclosing,key=lambda n:getattr(n,'end_lineno',n.lineno)-n.lineno)
            return f'Continuation/body of {type(n).__name__} starting at L{n.lineno}. Follow indentation and the owning symbol.'
    if path.endswith(('.jsx','.js')):
        if 'import ' in stripped:return 'Imports a module/component; local imports are linked above.'
        if 'function ' in stripped:return 'Declares a function/component. This physical line may also contain its JSX, handlers and return value; see the page walkthrough.'
        if 'useEffect(' in stripped:return 'Registers a React effect/lifecycle action; inspect dependencies and cleanup on this line/block.'
        if 'useState(' in stripped:return 'Declares React component state and its update function.'
        if 'useResource(' in stripped:return 'Connects a component to the resource hook/API path shown here.'
        if 'return ' in stripped:return 'Returns a value or JSX view. Conditions and mapped elements determine visible output.'
        return 'JavaScript/JSX statement or continuation. The owning component and exact source expression define its role.'
    if path.endswith('.css'):return 'CSS selectors and declarations control presentation, layout, responsive behavior or state styling.'
    if path.endswith(('.ps1','.cmd')):return 'Launcher command/configuration; executed by PowerShell or Windows command shell in order.'
    return 'Configuration, document structure or dependency declaration consumed by the associated runtime/tool.'

OUT.mkdir(parents=True,exist_ok=True)
template=(ROOT/'docs/project-walkthrough.template.md').read_text(encoding='utf-8')
resolved_links=[]
def link(match):
    ref=match[1];path,_,symbol=ref.partition('#')
    assert path in contents or (ROOT/path).is_file(),path
    line=1
    if symbol:
        found=next((s for s in symbols.get(path,[]) if s['name']==symbol),None)
        if not found:raise ValueError('Unresolved symbol '+ref)
        line=found['line']
    resolved_links.append({'file':path,'line':line,'symbol':symbol})
    return f'[{path}'+(f' — {symbol}' if symbol else '')+f']({(ROOT/path).as_posix()}:{line})'
guide=re.sub(r'\[\[([^\]]+)\]\]',link,template)
(OUT/'RegInsight-Project-Walkthrough.md').write_text(guide,encoding='utf-8')
try:
    from markdown_it import MarkdownIt
    linked=guide
    for ref in resolved_links:
        old=(ROOT/ref['file']).as_posix()+':'+str(ref['line'])
        if ref['file'] in ids:linked=linked.replace(old,'RegInsight-Code-Atlas.html#'+ids[ref['file']]+'-L'+str(ref['line']))
    rendered=MarkdownIt('commonmark').enable('table').render(linked)
    guide_html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RegInsight project walkthrough</title><style>body{max-width:1120px;margin:auto;padding:32px;font:17px/1.75 system-ui,sans-serif;color:#183541;background:#f8fafb}h1,h2,h3{line-height:1.3}h2{margin-top:48px;padding-top:22px;border-top:1px solid #cedde2}a{color:#176b87;overflow-wrap:anywhere}table{border-collapse:collapse;font-size:15px;display:block;overflow:auto}td,th{border:1px solid #ccdade;padding:10px;vertical-align:top}th{background:#e9f1f4}pre{white-space:pre-wrap;background:#edf3f5;padding:18px;overflow-wrap:anywhere}code{font-family:Consolas,monospace}p,li{max-width:100ch}.links{padding:14px;background:#e5f2f4}@media(max-width:600px){body{padding:18px;font-size:16px}}</style><div class="links"><a href="RegInsight-Code-Atlas.html">Open the searchable source atlas</a> · <a href="RegInsight-Project-Walkthrough.md">Markdown version with Mermaid diagrams</a></div>'''+rendered+'</html>'
    (OUT/'RegInsight-Project-Walkthrough.html').write_text(guide_html,encoding='utf-8')
except ImportError:
    pass

reverse=defaultdict(list)
for origin,deps in dependencies.items():
    for target in deps:reverse[target].append(origin)
def local_link(path,line=None,label=None):
    return '<a href="#'+ids[path]+(f'-L{line}' if line else '')+'">'+html.escape(label or path)+'</a>'
panels=[]
for path,source in contents.items():
    lines=source.splitlines();sid=ids[path]
    links=' · '.join(local_link(p) for p in dependencies[path]) or 'No resolved project-local import in this snapshot.'
    incoming=' · '.join(local_link(p) for p in reverse[path]) or 'No resolved static importer in the indexed source; may be an entry point, script, fixture or optional module.'
    index=' · '.join(local_link(path,s['line'],f"{s['name']} · L{s['line']}") for s in symbols[path]) or 'No named function/class declaration.'
    rows=''.join(f'<tr id="{sid}-L{i}"><td class="ln"><a href="#{sid}-L{i}">{i}</a></td><td><pre>{html.escape(line)}</pre></td><td class="note">{html.escape(note(path,i,line))}</td></tr>' for i,line in enumerate(lines,1))
    refs=' · '.join(local_link(path,c['line'],f"L{c['line']}: {c['expression']}") for c in calls[path])
    panels.append(f'<details class="file" id="{sid}"><summary>{html.escape(path)} <small>{len(lines)} lines</small></summary><div class="meta"><p><b>SHA-256:</b> {hashlib.sha256(source.encode()).hexdigest()}</p><p><b>Imports:</b> {links}</p><p><b>Imported by:</b> {incoming}</p><p><b>Symbols:</b> {index}</p><details><summary>Python static call expressions (not a runtime trace)</summary><p>{refs or "Not indexed for this file type."}</p></details></div><table><thead><tr><th>Line</th><th>Exact source</th><th>Structural reading note</th></tr></thead><tbody>{rows}</tbody></table></details>')
route_rows=''.join('<tr><td>'+r['method']+'</td><td><code>'+html.escape(r['route'])+'</code></td><td>'+local_link(r['file'],r['line'],r['handler']+' · '+r['file'])+'</td></tr>' for r in sorted(routes,key=lambda r:(r['route'],r['method'])))
document='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RegInsight • Code atlas</title>
<style>body{margin:0;background:#f6f8fa;color:#182e39;font:16px/1.6 system-ui,sans-serif}header,main{max-width:1600px;margin:auto;padding:24px}h1{font-size:32px;margin:0}a{color:#126481;text-underline-offset:3px}input{font:inherit;padding:12px;width:min(720px,90%);border:1px solid #9eb0ba;border-radius:4px}details.file{background:white;margin:12px 0;border:1px solid #cbd6dc;border-radius:6px;overflow:auto}summary{cursor:pointer;font-weight:700;padding:12px;overflow-wrap:anywhere}small{font-weight:400;color:#527080;margin-left:12px}.meta{padding:0 16px;overflow-wrap:anywhere}.meta a{display:inline-block;margin:2px}table{border-collapse:collapse;width:100%;font-size:14px}td,th{border-top:1px solid #dae2e6;vertical-align:top;text-align:left;padding:8px}th{background:#edf3f5}.ln{width:44px;font-variant-numeric:tabular-nums}pre{margin:0;font:13px/1.6 Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;word-break:break-word;min-width:300px}td.note{width:29%;min-width:170px;color:#3e5967}.flow{padding:16px;background:#e8f2f4;border-left:4px solid #25788b}tr:target{background:#fff2c7}button{font:inherit;padding:8px 14px;cursor:pointer}footer{padding:28px} @media(max-width:700px){header,main{padding:14px}td.note{min-width:130px}h1{font-size:25px}}</style>
<header><h1>RegInsight AI — Code atlas</h1><p>28 September 2026 · Read the <a href="RegInsight-Project-Walkthrough.md">project walkthrough</a> first.</p>
<p>Every indexed source line is preserved and numbered. Notes explain syntax and structure; the walkthrough explains business intent. Static imports/calls are not proof of runtime execution. The current frontend starts at main.jsx → Experience.jsx; The unmounted older App.jsx shell was removed during cleanup.</p>
<p class="flow">Source audit → canonicalization / quarantine → SQL + Parquet → summaries and observation snapshots → scoped API retrieval → React pages → source evidence → human review. DeepEval evaluates collected outputs separately.</p>
<label for="find">Find a file, function, API path or code expression</label><br><input id="find" placeholder="Try calculate_risk, workspace/reviews, useResource…"><p id="count"></p><button id="collapse">Collapse files</button></header><main>
<details><summary>API endpoint catalog (statically declared route decorators)</summary><p>Routes below are read from API source. Prefixes from APIRouter are included. The main application includes its routers; this catalog does not execute API mutations.</p><table><thead><tr><th>Method</th><th>Path</th><th>Handler / source</th></tr></thead><tbody>'''+route_rows+'''</tbody></table></details>'''+''.join(panels)+'''</main><footer>Local source snapshot • No external scripts or network requests.</footer>
<script>const files=[...document.querySelectorAll('.file')], search=document.getElementById('find'), count=document.getElementById('count');function filter(){const q=search.value.toLowerCase().trim();let n=0;for(const f of files){f.hidden=!!q&&!f.textContent.toLowerCase().includes(q);if(!f.hidden)n++;}count.textContent=n+' of '+files.length+' files shown';}search.addEventListener('input',filter);document.getElementById('collapse').onclick=()=>files.forEach(f=>f.open=false);function reveal(){if(!location.hash)return;const target=document.getElementById(decodeURIComponent(location.hash.slice(1)));if(!target)return;search.value='';filter();let p=target;while(p){if(p.tagName==='DETAILS')p.open=true;p=p.parentElement;}target.scrollIntoView({block:'center'});}window.addEventListener('hashchange',reveal);filter();reveal();</script></html>'''
(OUT/'RegInsight-Code-Atlas.html').write_text(document,encoding='utf-8')
manifest={'created':str(date.today()),'source_root':str(ROOT),'files':[{'path':p,'lines':len(s.splitlines()),'sha256':hashlib.sha256(s.encode()).hexdigest(),'symbols':symbols[p],'imports':dependencies[p]} for p,s in contents.items()],'endpoints':routes,'resolved_guide_links':resolved_links}
(OUT/'RegInsight-Code-Manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
assert len(set(ids.values()))==len(ids)
assert not re.search(r'\[\[[^\]]+\]\]',guide)
print(json.dumps({'files':len(contents),'lines':sum(len(s.splitlines()) for s in contents.values()),'symbols':sum(len(s) for s in symbols.values()),'api_routes':len(routes),'verified_guide_links':len(resolved_links),'output':str(OUT)}))
