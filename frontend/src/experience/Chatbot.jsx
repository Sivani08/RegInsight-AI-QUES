import React,{useEffect,useRef,useState} from 'react';
import {Send,Square,RotateCcw,PanelRightClose,MessageSquare,ArrowUpRight} from 'lucide-react';
import {request} from '../reginsight/data';
import './chatbot.css';

// Plain text only: model output never becomes HTML or an executable link.
function AnswerText({text}){return <div className="chat-answer-text">{text.split(/\n\s*\n/).map((p,i)=><p key={i}>{p}</p>)}</div>}
const seconds=ms=>ms<1000?`${ms} ms`:`${(ms/1000).toFixed(1)} s`;
export default function Chatbot({filters,close}){
  const [turns,setTurns]=useState([]),[draft,setDraft]=useState(''),[busy,setBusy]=useState(false),[status,setStatus]=useState(null),[error,setError]=useState('');
  const controller=useRef(null),history=useRef([]),context=useRef({}),end=useRef(null),session=useRef(null);
  const [loadingHistory,setLoadingHistory]=useState(true);
  function reset(){controller.current?.abort();controller.current=null;history.current=[];context.current={};session.current=null;setTurns([]);setBusy(false);setError('')}
  useEffect(()=>{
    reset();setLoadingHistory(true);
    const c=new AbortController();
    async function restore(){
      try{
        const sessions=await request('/chatbot/sessions',null,c.signal);
        const active=sessions.find(s=>Object.keys({...s.filters,...filters}).every(k=>(s.filters[k]??null)===(filters[k]??null)));
        if(!active)return;
        const saved=await request(`/chatbot/sessions/${active.id}`,null,c.signal);
        if(c.signal.aborted)return;
        session.current=active.id;
        setTurns(saved.messages.filter(m=>m.role==='user').map(question=>{
          const answer=saved.messages.find(m=>m.reply_to_id===question.id);
          return {id:question.id,question:question.content,answer:answer?.content,
            sources:answer?.sources||[],citations:answer?.citations||[],analytics:answer?.analytics,
            mode:answer?.response_mode,total_ms:answer?.latency_ms,
            status:answer?.status==='RUNNING'?'Response is running. Reopen to refresh.':''};
        }));
      }catch(e){if(!c.signal.aborted)setError('Saved conversation could not be loaded. Please reopen the assistant.')}
      finally{if(!c.signal.aborted)setLoadingHistory(false)}
    }
    restore();return()=>{c.abort();controller.current?.abort()};
  },[JSON.stringify(filters)]);
  useEffect(()=>{const c=new AbortController();request('/chatbot/status',null,c.signal).then(setStatus).catch(()=>setStatus({ready:false}));return()=>c.abort()},[]);
  useEffect(()=>{end.current?.scrollIntoView({block:'nearest',behavior:'instant'})},[turns]);
  async function send(question){
    if(!question.trim()||busy||loadingHistory)return;
    const c=new AbortController();controller.current=c;const id=crypto.randomUUID();
    setBusy(true);setDraft('');setError('');
    setTurns(old=>[...old.slice(-5),{id,question,status:'Retrieving RegInsight evidence…',sources:[]}]);
    const update=changes=>{if(controller.current===c&&!c.signal.aborted)setTurns(old=>old.map(t=>t.id===id?{...t,...changes}:t))};
    let completed=false;
    try{
      const response=await fetch('/api/chatbot/stream',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({question,filters,session_id:session.current,limit:3}),signal:AbortSignal.any([c.signal,AbortSignal.timeout(90000)])});
      if(!response.ok){const data=await response.json();throw new Error(typeof data.detail==='string'?data.detail:'Unable to submit this question.')}
      const reader=response.body.getReader(),decoder=new TextDecoder();let buffer='';
      function accept(line){
        if(!line.trim())return;const event=JSON.parse(line);
        if(event.type==='session'&&controller.current===c)session.current=event.session_id;
        if(event.type==='error')throw new Error(event.message);
        if(event.type==='status')update({status:event.message});
        if(event.type==='evidence'){
          update({sources:event.sources,analytics:event.analytics,retrieval_ms:event.retrieval_ms});
          if(controller.current===c&&event.analytics)context.current=event.analytics.context;
        }
        if(event.type==='answer'){
          completed=true;update({...event,status:''});
          if(controller.current===c&&!c.signal.aborted)history.current=[...history.current,{role:'user',content:question},{role:'assistant',content:event.answer}].slice(-8);
        }
      }
      try{while(true){const {value,done}=await reader.read();buffer+=decoder.decode(value||new Uint8Array(),{stream:!done});const lines=buffer.split('\n');buffer=lines.pop();lines.forEach(accept);if(done){if(buffer.trim())accept(buffer);break}}}
      finally{reader.releaseLock()}
      if(!completed)throw new Error('The connection ended before the answer completed. Please retry.');
    }catch(e){if(controller.current===c){if(!c.signal.aborted)setError(e.message);setTurns(old=>old.map(t=>t.id===id?{...t,status:c.signal.aborted?'Stopped. Retrieved evidence remains available.':'Answer could not be completed.'}:t))}}
    finally{if(controller.current===c)setBusy(false)}
  }
  const starters=['What does OAI mean?','What stands out in this dashboard?','How does RegInsight detect recurring risks?','Is this model trained on our data?'];
  return <aside className="copilot reginsight-chat" aria-label="RegInsight chatbot">
    <header><div><span className="copilot-icon"><MessageSquare size={18}/></span><h2>RegInsight assistant<small>Local Ollama · Graph + general questions</small></h2></div><button className="icon-button" onClick={reset} aria-label="Reset chatbot"><RotateCcw size={18}/></button><button className="icon-button" onClick={close} aria-label="Close assistant"><PanelRightClose size={18}/></button></header>
    <div className="chat-model-status"><span className={status?.ready?'status-dot':''}/><strong>{status?.ready?'Local model ready':status?'Local model unavailable':'Checking local model…'}</strong><small>{status?.model||'RegInsight Qwen'} · {Object.entries(filters).map(([k,v])=>`${k}: ${v}`).join(' · ')||'All portfolio records'}</small></div>
    <div className="conversation" aria-live="polite" aria-relevant="additions text">
      {!turns.length&&<div className="copilot-welcome"><h3>Ask. Understand.<br/>Check the evidence.</h3><p>Explore your dashboard, ask about RegInsight, or get help with general questions.</p>{starters.map(q=><button key={q} onClick={()=>send(q)}>{q}<ArrowUpRight size={16}/></button>)}<p className="chat-disclosure">Configured for RegInsight with retrieved evidence. Base model weights are not fine-tuned.</p></div>}
      {turns.map(t=><article className="answer chat-turn" key={t.id}><div className="user-question">{t.question}</div>
        <div className="answer-label">{t.mode==='local_llm'?'LOCAL MODEL · SOURCE-LINKED':t.mode==='evidence_only'?'RETRIEVED EVIDENCE · MODEL FALLBACK':t.mode==='insufficient_evidence'?'EVIDENCE NOT FOUND':'REGINSIGHT ASSISTANT'}</div>
        {t.answer&&<AnswerText text={t.answer}/>}
        {t.status&&<p className="chat-progress" role="status">{t.status}</p>}
        {t.analytics&&<details className="chat-calculated" open><summary>Calculated result</summary><strong>{t.analytics.headline}</strong>{t.analytics.insights.filter(i=>i.type==='fact').slice(0,4).map((i,n)=><p key={n}>{i.statement}</p>)}<small>Evidence ID: {t.analytics.evidence_id}</small></details>}
        {t.sources.length>0&&<details className="chat-sources" open><summary>Sources ({t.sources.length})</summary>{t.sources.map(s=><details key={s.id} className="chat-source"><summary><span className="chat-source-id">{s.id}</span> {s.title}{t.citations?.includes(s.id)&&<small> · cited</small>}</summary><p>{s.text}</p><small>{s.kind} · {s.locator}</small>{s.scope&&<small>Scope: {JSON.stringify(s.scope.filters||{})} · As of {s.scope.as_of}</small>}</details>)}</details>}
        {t.retrieval_ms!=null&&<div className="chat-timing"><span>Evidence {seconds(t.retrieval_ms)}</span>{t.total_ms!=null&&<span>Answer {seconds(t.total_ms)}</span>}</div>}
        {t.mode==='local_llm'&&<p className="chat-disclosure">Source IDs and numeric tokens checked. Review the cited evidence; these checks do not verify every claim.</p>}
      </article>)}
      {error&&<p className="rx-error" role="alert">{error}</p>}<div ref={end}/>
    </div>
    <form className="copilot-compose" onSubmit={e=>{e.preventDefault();send(draft)}}><label className="sr-only" htmlFor="chat-question">Ask RegInsight</label><textarea id="chat-question" value={draft} onChange={e=>setDraft(e.target.value)} rows={2} maxLength={4000} placeholder="Ask about the graph—or anything else…" onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.nativeEvent.isComposing){e.preventDefault();send(draft)}}}/><div><small>Local inference. Human judgment.</small>{busy?<button type="button" className="send-button" onClick={()=>controller.current?.abort()} aria-label="Stop answer"><Square size={16}/></button>:<button className="send-button" disabled={!draft.trim()} aria-label="Send chatbot question"><Send size={18}/></button>}</div></form>
  </aside>
}
