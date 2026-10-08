import React, {useId} from 'react';
import {number, shortNumber, riskLabel} from './data';

export function Trend({rows = []}) {
  const id = useId();
  if (!rows.length) return <p className="ri-empty">No dated observations in this scope.</p>;
  const width = 650, height = 188, max = Math.max(1, ...rows.map(r => r.observations));
  const x = i => 45 + i * 590 / Math.max(1, rows.length - 1);
  const y = n => height - 24 - n / max * 135;
  return <figure className="ri-trend">
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-labelledby={id}>
      <title id={id}>Observation count by fiscal year. {rows.map(r => `${r.year}: ${number(r.observations)}`).join('; ')}</title>
      {[0, .5, 1].map(n => <g key={n}><line x1="45" x2="635" y1={y(max*n)} y2={y(max*n)} className="ri-gridline"/><text x="36" y={y(max*n)+4} textAnchor="end">{shortNumber(max*n)}</text></g>)}
      <path d={rows.map((r,i) => `${i ? 'L' : 'M'}${x(i)},${y(r.observations)}`).join(' ')} fill="none" stroke="var(--blue)" strokeWidth="2.3"/>
      {rows.map((r,i) => <g key={r.year}><circle cx={x(i)} cy={y(r.observations)} r="3" fill="var(--blue)"><title>{r.year}: {number(r.observations)} observations</title></circle>{(i===0 || i===rows.length-1 || i%Math.max(1,Math.ceil(rows.length/7))===0) && <text x={x(i)} y="185" textAnchor="middle">{r.year}</text>}</g>)}
    </svg>
    <figcaption>Fiscal year · Source observation records. Partial periods may affect comparisons.</figcaption>
    <details><summary>View chart data</summary><table><thead><tr><th>Fiscal year</th><th>Observations</th><th>Inspections</th></tr></thead><tbody>{rows.map(r => <tr key={r.year}><th>{r.year}</th><td>{number(r.observations)}</td><td>{number(r.inspections)}</td></tr>)}</tbody></table></details>
  </figure>;
}

export function Bars({rows = [], semantic = false, onSelect, suffix = ''}) {
  const max = Math.max(1, ...rows.map(r => r.count));
  return rows.length ? <div className="ri-bars">{rows.map(r => <div className="ri-bar-row" key={r.label}>
    <div>{onSelect ? <button className="ri-text-button" onClick={() => onSelect(r.label)}>{r.label}</button> : <span>{r.label}</span>}<b>{number(r.count)}{suffix}</b></div>
    <div className="ri-bar-track" aria-hidden="true"><span className={semantic ? riskLabel(r.label) : ''} style={{width: `${r.count / max * 100}%`}}/></div>
  </div>)}</div> : <p className="ri-empty">No records available in this scope.</p>;
}
