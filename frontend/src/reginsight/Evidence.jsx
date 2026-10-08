import React, {useEffect, useState} from 'react';
import {dateTime, request, useResource, queryString, riskLabel} from './data';
import WorkflowReview from './WorkflowReview';

export function Status({value}) { return <span className={`ri-status ${riskLabel(value)}`}>{value || 'Unclassified'}</span>; }

export function Source({record, compact = false}) {
  if (!record) return <div className="ri-empty">Select an observation to inspect its source, assessment and review history.</div>;
  const tag = record.tag;
  return <>
    <div className="ri-evidence-heading"><span className="ri-overline">Source observation</span><Status value={tag.severity}/></div>
    <blockquote className={compact ? 'ri-quote compact' : 'ri-quote'}>{record.original_text}</blockquote>
    <dl className="ri-facts">
      <div><dt>Category</dt><dd>{tag.category}</dd></div>
      <div><dt>Theme</dt><dd>{tag.theme}</dd></div>
      <div><dt>Severity</dt><dd>{tag.severity} · analytical</dd></div>
      <div><dt>Risk</dt><dd>Not scored at observation level</dd></div>
      <div><dt>Recurrence</dt><dd>{record.related_inspections == null ? 'Open related evidence' : record.related_inspections > 1 ? `Related text across ${record.related_inspections.toLocaleString()} inspections` : 'One linked inspection'}</dd></div>
      {!compact && <><div><dt>Assessment</dt><dd>{tag.ai_generated ? 'AI-assisted classification' : 'Deterministic classification'}</dd></div><div><dt>Confidence</dt><dd>{Math.round(tag.confidence*100)}% · uncalibrated</dd></div><div><dt>Provider / model</dt><dd>{tag.provider} / {tag.model}</dd></div><div><dt>Assessed</dt><dd>{dateTime(tag.timestamp)}</dd></div></>}
    </dl>
    <div className="ri-source-reference"><span className="ri-overline">Evidence reference</span><strong>{record.source_file?.split(/[\\/]/).at(-1)}</strong><span>{record.source_sheet ? `${record.source_sheet} · ` : ''}Row {record.source_row || 'not supplied'}</span>{!compact && <small>{record.observation_id}</small>}</div>
  </>;
}

export function Review({record, runId, onSaved}) {
  const [version, setVersion] = useState(0);
  const history = useResource(record && runId ? '/workspace/reviews?' + queryString({run_id: runId, observation_id: record.observation_id}) : null, version);
  const [action, setAction] = useState('Approve'), [reviewer, setReviewer] = useState(''), [note, setNote] = useState('');
  const [theme, setTheme] = useState(record?.tag.theme || ''), [severity, setSeverity] = useState(record?.tag.severity || 'High');
  const [saving, setSaving] = useState(false), [message, setMessage] = useState(''), [error, setError] = useState('');
  useEffect(() => {setTheme(record?.tag.theme || ''); setSeverity(record?.tag.severity || 'High'); setNote(''); setMessage(''); setError(''); setAction('Approve');}, [record?.observation_id]);
  if (!record) return <p className="ri-empty">Select an observation in the workspace to begin a review.</p>;
  async function save(event) {
    event.preventDefault(); setSaving(true); setError(''); setMessage('');
    try {
      await request('/workspace/reviews', {run_id: runId, observation_id: record.observation_id, revision: history.data?.[0]?.revision || 0, action, reviewer, note, theme: action==='Modify' ? theme : null, severity: action==='Modify' ? severity : null});
      setMessage('Review recorded. The original assessment is preserved.'); setVersion(v => v+1); onSaved?.(); setNote('');
    } catch(e) { setError(e.message); setVersion(v => v+1); }
    finally { setSaving(false); }
  }
  return <div className="ri-review">
    <div className="ri-section-heading"><h3>Expert review</h3><span className="ri-mono">{history.data?.length || 0} decisions recorded</span></div>
    <p className="ri-muted">Confirm the evidence, adjust the interpretation, or reject the assessment.</p>
    <form onSubmit={save}>
      <fieldset className="ri-decision"><legend>Reviewer decision</legend>{['Approve','Modify','Reject'].map(v => <label key={v} className={action===v ? 'selected' : ''}><input type="radio" name="decision" value={v} checked={action===v} onChange={() => setAction(v)}/>{v}</label>)}</fieldset>
      {action==='Modify' && <div className="ri-form-pair"><label>Proposed theme<input required maxLength={150} value={theme} onChange={e => setTheme(e.target.value)}/></label><label>Proposed severity<select value={severity} onChange={e => setSeverity(e.target.value)}>{['Low','Medium','High','Critical','Unclassified'].map(v => <option key={v}>{v}</option>)}</select></label></div>}
      <label>Reviewer name<input required autoComplete="name" maxLength={100} value={reviewer} onChange={e => setReviewer(e.target.value)} placeholder="Enter your name"/></label>
      <label>Review rationale<textarea required maxLength={2000} rows={3} value={note} onChange={e => setNote(e.target.value)} placeholder="Explain the decision and the evidence considered."/></label>
      <p className="ri-note">Local review record. Reviewer identity is self-reported; this is not an authenticated electronic signature.</p>
      <button className="ri-button primary" disabled={saving || history.loading || Boolean(history.error)}>{saving ? 'Saving review…' : 'Record decision'}</button>
      {message && <p role="status" className="ri-success">{message}</p>}{(error || history.error) && <p role="alert" className="ri-error">{error || history.error}</p>}
    </form>
    <details className="ri-history" open={Boolean(history.data?.length)}><summary>Review history</summary>{history.data?.length ? <ol>{history.data.map(item => <li key={item.revision}><div><strong>{item.action}</strong><span>{dateTime(item.timestamp)}</span></div><p>{item.note}</p><small>{item.reviewer} · revision {item.revision}</small>{item.action==='Modify' && <p>Proposed: {item.theme} / {item.severity}</p>}</li>)}</ol> : <p className="ri-note">No human decisions have been recorded for this observation and snapshot.</p>}</details>
    <WorkflowReview record={record} runId={runId}/>
  </div>;
}
