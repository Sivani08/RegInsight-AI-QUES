import React, {useEffect, useState} from 'react';
import {request, useResource} from './data';

// Reuses the existing evidence/review section and CSS; no new page or navigation.
export default function WorkflowReview({record, runId}) {
  const [question,setQuestion]=useState(''),[id,setId]=useState(''),[version,setVersion]=useState(0);
  const [reviewer,setReviewer]=useState(''),[comment,setComment]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState(''),[modified,setModified]=useState('');
  const state=useResource(id?'/workflows/'+encodeURIComponent(id):null,version);
  const pending=useResource('/workflows/reviews/pending',version);
  const w=state.data, artifact=w?.artifacts?.at(-1);
  const running=w&&['RECEIVED','ROUTED','RETRIEVING','GENERATING','EVALUATING','REVISION_REQUIRED','APPROVED'].includes(w.status);
  useEffect(()=>{if(!running)return;const timer=setInterval(()=>setVersion(v=>v+1),2500);return()=>clearInterval(timer)},[running]);
  useEffect(()=>{setQuestion(record?'Summarise this inspection observation and explain the supported quality concern: '+record.original_text.slice(0,350):'');},[record?.observation_id]);
  async function start(e){
    e.preventDefault();setBusy(true);setError('');
    try{const value=await request('/workflows',{question,observation_id:record.observation_id,run_id:runId,require_review:true});setId(value.workflow_id);setVersion(v=>v+1)}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  async function decide(action){
    if(!reviewer.trim()||!comment.trim()){setError('Reviewer name and rationale are required.');return;}
    setBusy(true);setError('');
    try{await request('/workflows/'+encodeURIComponent(id)+'/reviews/'+action,{artifact_version:artifact.version,workflow_revision:w.revision,idempotency_key:crypto.randomUUID(),reviewer,comment,...(action==='modify'?{modified_output:modified}:{})});setVersion(v=>v+1);setComment('')}
    catch(e){setError(e.message)}finally{setBusy(false)}
  }
  return <details className="ri-history"><summary>AI assessment and workflow review</summary>
    <p className="ri-note">Create a source-linked draft and model evaluation. The final assessment stays blocked until the latest draft is approved. Reviewer identity is verified through your signed-in account.</p>
    {record&&<form onSubmit={start}><label>Assessment question<textarea required minLength={3} maxLength={4000} rows={3} value={question} onChange={e=>setQuestion(e.target.value)}/></label><button className="ri-button" disabled={busy||running}>Start AI assessment</button></form>}
    {pending.data?.length>0&&<label>Pending assessments<select value={id} onChange={e=>{setId(e.target.value);setVersion(v=>v+1)}}><option value="">Select an assessment</option>{pending.data.map(x=><option value={x.workflow_id} key={x.workflow_id}>{x.request.question.slice(0,100)}</option>)}</select></label>}
    {(error||state.error||pending.error)&&<p role="alert" className="ri-error">{error||state.error||pending.error}</p>}
    {w&&<div aria-live="polite"><p><strong>Status:</strong> {w.status.replaceAll('_',' ')}</p><p className="ri-note">Workflow {w.workflow_id}</p>
      <p><strong>Original question:</strong> {w.request.question}</p>
      {w.routing&&<><p><strong>Selected agent:</strong> {w.routing.selected_agent}{w.routing.secondary_agents.length?' + '+w.routing.secondary_agents.join(', '):''}</p><p>{w.routing.routing_reason}</p><p><strong>Risk:</strong> {w.analysis.risk_level} · Agent confidence: not calibrated</p></>}
      {artifact&&<><h4>Draft assessment · version {artifact.version}</h4><p style={{whiteSpace:'pre-wrap'}}>{artifact.content}</p>{artifact.limitations.map((s,i)=><p className="ri-note" key={i}>{s}</p>)}
        <h4>Model evaluation</h4><p>{artifact.evaluation.overall_score}/100 · {artifact.evaluation.decision} · {artifact.evaluation.model}</p><dl className="ri-facts">{Object.entries(artifact.evaluation.dimensions).map(([k,v])=><div key={k}><dt>{k.replaceAll('_',' ')}</dt><dd>{v}/10</dd></div>)}</dl><p>{artifact.evaluation.rationale}</p>{artifact.evaluation.issues.map((s,i)=><p key={i}>{s}</p>)}{artifact.evaluation.same_model&&<p className="ri-note">A separate judge call uses the same model as generation; correlated errors remain possible.</p>}</>}
      {w.retrieval_trace&&<details><summary>Retrieved evidence · {w.retrieval_trace.retrieval_status}</summary>{w.retrieval_trace.results.map(r=><div key={r.chunk.chunk_id}><strong>{r.chunk.document_name}</strong><p className="ri-note">{r.chunk.chunk_id} · cosine {r.similarity_score.toFixed(3)} · {w.retrieval_trace.final_chunk_ids.includes(r.chunk.chunk_id)?'Used in context':'Candidate only'}{r.chunk.page_number?' · page '+r.chunk.page_number:''}{r.chunk.metadata.source_row?' · row '+r.chunk.metadata.source_row:''}</p><blockquote>{r.chunk.chunk_text}</blockquote></div>)}</details>}
      {w.status==='AWAITING_HUMAN_REVIEW'&&<><label>Reviewer name<input required maxLength={100} value={reviewer} onChange={e=>setReviewer(e.target.value)}/></label><label>Review rationale<textarea required rows={3} maxLength={2000} value={comment} onChange={e=>setComment(e.target.value)}/></label><label>Modified assessment (for Modify)<textarea rows={4} maxLength={10000} value={modified} onChange={e=>setModified(e.target.value)}/></label><div className="ri-form-pair">{[['approve','Approve'],['modify','Modify'],['reject','Reject']].map(([a,t])=><button className="ri-button" key={a} disabled={busy} onClick={()=>decide(a)}>{t}</button>)}</div></>}
      {w.error&&<p className="ri-error">{w.error}</p>}{w.final_response&&<><h4>Final response</h4><p style={{whiteSpace:'pre-wrap'}}>{w.final_response}</p></>}
      {w.reviews.map((r,i)=><p key={i}>{r.decision} · version {r.artifact_version} · {r.reviewer} · {r.timestamp}<br/>{r.comment}</p>)}
      <a href={'/api/workflows/'+encodeURIComponent(id)+'/trace'} target="_blank" rel="noreferrer">Open complete operational trace</a>
    </div>}
  </details>;
}
