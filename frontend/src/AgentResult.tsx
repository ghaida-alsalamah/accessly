import { useState } from "react";
import { displayText, type Draft, type AgentPresentation, type RequestRecord } from "./presentation";

export function StatusBadge({ status }: { status: string }) {
  const normalized = status.toUpperCase();
  const tone = normalized === 'CONFIRMED' ? 'positive' : ['PENDING', 'NOT CONFIRMED', 'PARTIALLY CONFIRMED', 'MORE INFORMATION NEEDED'].includes(normalized) ? 'attention' : normalized === 'UNAVAILABLE' ? 'negative' : 'neutral';
  return <span className={`status-badge ${tone}`}>{status.toLowerCase().replace(/\b\w/g, c => c.toUpperCase())}</span>;
}
export function ReadableText({ text }: { text: string }) {
  return <div className="readable-text">{displayText(text).split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>;
}
export function RequestStatus({ request }: { request: RequestRecord }) {
  return <section className="result-card"><div className="section-heading"><h2>Request Status</h2><StatusBadge status={request.status}/></div><p className="eyebrow">{request.request_id}</p><h3>{request.event_name}</h3><div className="needs-list">{Object.entries(request.accommodations).map(([name, status]) => <div className="section-heading need-row" key={name}><span>{name}</span><StatusBadge status={status}/></div>)}</div></section>;
}
function ContactValue({ value }: { value: string | null }) {
  if (!value) return <>Not stated by the organizer</>;
  const url = value.match(/https?:\/\/[^\s<>]+/)?.[0];
  return url ? <a href={url} target="_blank" rel="noopener noreferrer">{displayText(value)}</a> : <>{displayText(value)}</>;
}
function DraftCard({ draft, disabled, onReply }: { draft: Draft; disabled: boolean; onReply?: (text: string) => void }) {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(draft);
  const [submitted, setSubmitted] = useState(false);
  function send(approve: boolean) {
    if (!onReply || disabled || submitted) return;
    setSubmitted(true);
    onReply(`${approve ? 'I explicitly approve sending this exact email once' : 'Please revise the draft to the following exact content. Do not send it. Show the revised draft with To, Subject, and Body labels for my approval'}:\nTo: ${value.to}\nSubject: ${value.subject}\nBody:\n${value.body}`);
  }
  return <section className="result-card draft-card"><div className="section-heading"><h2>Email Draft</h2><span className="eyebrow">Your approval required</span></div>
    {editing ? <form onSubmit={e => { e.preventDefault(); send(false); }}>
      <label>To<input aria-label="To" type="email" required value={value.to} onChange={e => setValue({ ...value, to: e.target.value })} disabled={disabled || submitted} /></label>
      <label>Subject<input aria-label="Subject" required value={value.subject} onChange={e => setValue({ ...value, subject: e.target.value })} disabled={disabled || submitted} /></label>
      <label>Message<textarea aria-label="Message" required rows={10} value={value.body} onChange={e => setValue({ ...value, body: e.target.value })} disabled={disabled || submitted} /></label>
      <div className="button-row"><button className="primary-button" disabled={disabled || submitted}>Review revised draft</button><button type="button" className="secondary-button" onClick={() => { setValue(draft); setEditing(false); }} disabled={disabled || submitted}>Cancel</button></div>
    </form> : <><dl className="draft-meta"><dt>To</dt><dd>{draft.to}</dd><dt>Subject</dt><dd>{draft.subject}</dd></dl><div className="email-body">{draft.body}</div>
      {onReply && <><p className="helper-text">Review the exact message before approving. Development email delivery uses the configured test inbox.</p><div className="button-row"><button className="secondary-button" onClick={() => setEditing(true)} disabled={disabled || submitted}>Edit</button><button className="primary-button" onClick={() => send(true)} disabled={disabled || submitted}>{submitted ? 'Submitted for processing' : 'Approve & Send'}</button></div></>}
    </>}
  </section>;
}
export default function AgentResult({ result, disabled = false, onReply, onRetry }: { result?: AgentPresentation; disabled?: boolean; onReply?: (text: string) => void; onRetry?: () => void }) {
  if (!result || result.presentation_status !== 'ready') return <div className="error-card" role="alert"><h2>Result display unavailable</h2><p>{result?.message || 'This response needs to be formatted before it can be displayed.'}</p>{onRetry && <button className="secondary-button" onClick={onRetry} disabled={disabled}>Retry formatting</button>}</div>;
  const event = result.event;
  const action = result.recommended_action;
  const showEvent = event && Object.entries(event).some(([key, value]) => key !== 'url' && value) || result.accessibility_results.length > 0;
  const fields = [['name', 'Event Name'], ['date', 'Date'], ['time', 'Time'], ['location', 'Location'], ['organizer', 'Organizer'], ['format', 'Format']] as const;
  return <div className="structured-result">
    {result.message && <div className="agent-summary"><span className="eyebrow">Accessly</span><ReadableText text={result.message}/></div>}
    <div className="result-grid">
      {showEvent && <section className="result-card event-card" aria-label="Event Details"><h2>Event Details</h2><dl className="event-details">{fields.map(([key, label]) => <div key={key} data-event-field={key}><dt>{label}</dt><dd>{event?.[key] ? displayText(event[key]) : 'Not stated by the organizer'}</dd></div>)}</dl></section>}
      {result.accessibility_results.length > 0 && <section className="result-card accessibility-card"><h2>Accessibility Check</h2><div className="needs-list">{result.accessibility_results.map(need => <div className="need-row" key={need.name} data-need={need.name}><div className="section-heading"><h3>{need.name}</h3><StatusBadge status={need.status}/></div><ReadableText text={need.evidence}/></div>)}</div></section>}
      {action && Object.values(action).some(Boolean) && <section className="result-card action-card"><h2>Request Action</h2><dl className="action-details"><dt>Official contact / form</dt><dd><ContactValue value={action.official_contact || action.official_form}/>{action.official_contact && action.official_form && <p><ContactValue value={action.official_form}/></p>}</dd><dt>Notice period</dt><dd>{action.notice_period ? displayText(action.notice_period) : 'No accommodation notice period stated'}</dd><dt>Recommended action</dt><dd>{action.recommendation ? displayText(action.recommendation) : 'Ask Accessly about the next step.'}</dd></dl></section>}
      {result.draft && <DraftCard key={JSON.stringify(result.draft)} draft={result.draft} disabled={disabled} onReply={onReply}/>}
      {result.requests.map(request => <RequestStatus key={request.request_id} request={request}/>)}
    </div>
  </div>;
}
