import React, {useState} from 'react';
import {request, number, dateTime} from './data';

const questions = ['Show recurring high-severity observations.', 'Which regulatory themes increased between FY 2023 and FY 2024?', 'Find observations similar to this issue.', 'Why was this observation classified as high risk?', 'Show the evidence supporting this classification.'];

export default function Assistant({selected, onSelect}) {
  const [question,setQuestion] = useState(''), [answer,setAnswer] = useState(null), [error,setError] = useState(''), [busy,setBusy] = useState(false);
  async function ask(event) {
    event.preventDefault(); if (!question.trim() || busy) return;
    setBusy(true); setError(''); setAnswer(null);
    let q = question;
    if (/this (issue|observation|classification)/i.test(q)) {
      if (!selected) {setError('Select an observation in the workspace to provide context.'); setBusy(false); return;}
      q += ' Observation ' + selected.observation_id;
    }
    try {
      const result = await request('/agent/query', {question:q});
      const evidence = await request('/evidence/' + encodeURIComponent(result.analysis_id));
      setAnswer({...result, records:evidence.records || []});
    } catch(e) {setError(e.message);} finally {setBusy(false);}
  }
  const analyses = answer?.observation_intelligence;
  return <section id="assistant" className="ri-section ri-assistant">
    <div className="ri-section-intro"><span className="ri-overline">05 / Guided investigation</span><h2>Ask a question.<br/>Follow the evidence.</h2><p>Investigate patterns in natural language. Inspect the source records behind the answer before reaching a conclusion.</p><p className="ri-note">The assistant uses bounded tool routing. Numeric results come from dataset queries; unsupported questions request clarification.</p></div>
    <div className="ri-assistant-console"><div className="ri-section-heading"><h3>Inspection intelligence assistant</h3><span className="ri-mono">Evidence-linked</span></div>
      <div className="ri-prompts">{questions.map(q => <button key={q} onClick={() => setQuestion(q)}>{q}</button>)}</div>
      <form onSubmit={ask}><label htmlFor="question">Investigation question</label><textarea id="question" maxLength={2000} required rows={3} value={question} onChange={e => setQuestion(e.target.value)} placeholder="Ask about an inspection, theme, or selected observation…"/><div className="ri-assistant-submit"><span className="ri-note">{selected ? `Context available: ${selected.tag.theme}` : 'No observation selected'}</span><button className="ri-button primary" disabled={busy}>{busy ? 'Retrieving evidence…' : 'Investigate'}</button></div></form>
      {error && <p className="ri-error" role="alert">{error}</p>}
      {answer && <div className="ri-answer" aria-live="polite"><span className="ri-overline">Investigation result</span><h4>{answer.question}</h4>
        {analyses && Object.entries(analyses).filter(([,v]) => v?.records).map(([key,v]) => <p key={key}><strong>{number(v.total)}</strong> matching {key === 'similar' ? 'related observations in this bounded result' : 'observations'} in the selected snapshot. Showing {v.records.length} evidence records.</p>)}
        {analyses?.theme_changes && <div className="ri-table-scroll"><table><caption>Changes in inspection counts by theme</caption><thead><tr><th>Theme</th><th>Start</th><th>End</th><th>Change</th></tr></thead><tbody>{analyses.theme_changes.slice(0,8).map(r => <tr key={r.theme}><td>{r.theme}</td><td>{r.start_inspections}</td><td>{r.end_inspections}</td><td>{r.change>0?'+':''}{r.change}</td></tr>)}</tbody></table></div>}
        {answer.results?.map((r,i) => <p key={i}>{r.answer}</p>)}
        {answer.records[0]?.tag && <div className="ri-agent-assessment"><span className="ri-overline">Assessment in evidence record E01</span><h4>{answer.records[0].tag.theme} · {answer.records[0].tag.severity}</h4><p>{answer.records[0].tag.rationale}</p><blockquote className="ri-quote">{answer.records[0].tag.evidence_quote}</blockquote><p className="ri-note">{answer.records[0].tag.ai_generated ? 'AI-assisted' : 'Rule-derived'} interpretation. This example is one returned record, not a conclusion about the entire result set.</p></div>}
        <p className="ri-note">Analytical severity and portfolio risk are separate measures. Related text is a review candidate, not proof of a recurring regulatory finding.</p>
        <div className="ri-evidence-list">{answer.records.slice(0,6).map((r,i) => <button key={r.observation_id || r.inspection_id} onClick={() => r.tag && onSelect(r)} disabled={!r.tag}><span className="ri-mono">E{String(i+1).padStart(2,'0')}</span><span>{r.tag?.theme || r.company_name}<small>{r.source_file?.split(/[\\/]/).at(-1) || r.inspection_id} · {r.source_row ? `row ${r.source_row}` : 'inspection record'}</small></span><span aria-hidden="true">↗</span></button>)}</div>
        {!answer.records.length && <p>No source records were returned for this scope.</p>}
        <div className="ri-answer-footer"><span>{dateTime(answer.created_at)}</span><a href={'/api/evidence/'+encodeURIComponent(answer.analysis_id)} target="_blank" rel="noreferrer">Open complete evidence record</a></div>
      </div>}
    </div>
  </section>;
}
