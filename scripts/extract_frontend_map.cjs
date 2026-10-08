// Documentation only: parse JS/JSX with the project's existing Babel parser.
const fs=require('fs'),path=require('path');
const root=path.resolve(__dirname,'..'),out=path.resolve(root,'../../outputs');
const parser=require(path.join(root,'frontend/node_modules/@babel/parser'));
const manifest=JSON.parse(fs.readFileSync(path.join(out,'RegInsight-Code-Manifest.json'),'utf8'));
const result={};
for(const entry of manifest.files.filter(f=>/\.(jsx|js)$/.test(f.path))){
 const source=fs.readFileSync(path.join(root,entry.path),'utf8');
 const tree=parser.parse(source,{sourceType:'unambiguous',plugins:['jsx']});
 const symbols=[],calls=[],imports=[];
 const slice=n=>n?source.slice(n.start,n.end):'';
 function walk(n,parent,owner,scope){
  if(!n||typeof n!=='object'||!n.type)return;
  let active=owner,sc=scope;
  if(['FunctionDeclaration','FunctionExpression','ArrowFunctionExpression','ObjectMethod','ClassMethod'].includes(n.type)){
   let name=n.id?.name||n.key?.name||(parent?.type==='VariableDeclarator'?slice(parent.id):null)||`callback@${n.loc.start.line}:${n.loc.start.column}`;
   const qualified=[...scope,name].join('.'),id=entry.path+'#'+qualified+'@'+n.start;
   symbols.push({id,name:qualified,leaf:name,kind:n.type,start:n.loc.start.line,end:n.loc.end.line,params:n.params.map(slice).join(', '),doc:'',returns:[],conditions:[],raises:[]});
   active=id;sc=[...scope,name];
  }
  if(n.type==='ClassDeclaration')sc=[...scope,n.id?.name||'class'];
  if(n.type==='ImportDeclaration')imports.push({module:n.source.value,line:n.loc.start.line,bindings:n.specifiers.map(s=>({local:s.local.name,imported:s.imported?.name||s.imported?.value||(s.type==='ImportDefaultSpecifier'?'default':'*')}))});
  if(n.type==='CallExpression'||n.type==='NewExpression')calls.push({owner:active,line:n.loc.start.line,expression:slice(n.callee),kind:n.type});
  if(n.type==='JSXOpeningElement'&&/^[A-Z]/.test(slice(n.name)))calls.push({owner:active,line:n.loc.start.line,expression:slice(n.name),kind:'JSX component'});
  const record=symbols.find(s=>s.id===active);
  if(record&&n.type==='ReturnStatement')record.returns.push(slice(n.argument).slice(0,180));
  if(record&&n.type==='IfStatement')record.conditions.push(slice(n.test).slice(0,160));
  if(record&&n.type==='ThrowStatement')record.raises.push(slice(n.argument).slice(0,160));
  for(const [key,value] of Object.entries(n)){
   if(['loc','start','end','comments','tokens','extra'].includes(key))continue;
   if(Array.isArray(value)){for(const child of value)walk(child,n,active,sc);}else if(value&&typeof value==='object')walk(value,n,active,sc);
  }
 }
 walk(tree,null,'<module>',[]);result[entry.path]={symbols,calls,imports};
}
fs.writeFileSync(path.join(out,'RegInsight-Frontend-Symbols.json'),JSON.stringify(result,null,2));
console.log('Parsed JS/JSX files:',Object.keys(result).length,'functions including callbacks:',Object.values(result).reduce((n,v)=>n+v.symbols.length,0));
