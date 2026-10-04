import { useEffect, useRef, useState } from "react";
import { api, waitForJob, type Job, type TrackedRequest } from "./api";
import type { AgentPresentation } from "./presentation";
import AgentResult, { StatusBadge, ReadableText } from "./AgentResult";

type Turn = { role: 'user' | 'agent'; text: string; result?: AgentPresentation; jobId?: string };
type Saved = { job: Job | null; turns: Turn[]; needs: string[] };
export default function AgentWorkspace({ url, onBack, onDone }: { url: string; onBack: () => void; onDone: () => void }) {
  const key = `accessly:conversation:v2:${url}`;
  const [job, setJob] = useState<Job | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [needs, setNeeds] = useState<string[]>([]);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [answer, setAnswer] = useState('');
  const [success, setSuccess] = useState('');
  const [action, setAction] = useState('check');
  const started = useRef(false);
  const inFlight = useRef(false);
  const state = useRef<Saved>({ job: null, turns: [], needs: [] });
  function persist() { try { sessionStorage.setItem(key, JSON.stringify(state.current)); } catch { /* Storage is optional; current conversation remains usable. */ } }
  function addTurn(turn: Turn) { state.current.turns = [...state.current.turns, turn]; setTurns(state.current.turns); persist(); }
  async function run(message?: string, existing?: Job) {
    if (inFlight.current) return;
    inFlight.current = true; setBusy(true); setError(''); setSuccess('');
    const approving = message?.startsWith('I explicitly approve sending this exact email once');
    setAction(approving ? 'send' : message ? 'reply' : 'check');
    if (message) addTurn({ role: 'user', text: message });
    try {
      // Request records are the confirmation source; prose alone never creates a success banner.
      const before = approving ? await api<TrackedRequest[]>('/requests') : [];
      const next = existing ?? await api<Job>(message ? `/sessions/${state.current.job?.session_id}/messages` : '/events', 'POST', message ? { message } : { url });
      const result = await waitForJob(next, value => { state.current.job = value; setJob(value); persist(); });
      if (result.status === 'failed') { setError(result.response); return; }
      addTurn({ role: 'agent', text: result.result?.message || '', result: result.result, jobId: result.id });
      if (approving) {
        const after = await api<TrackedRequest[]>('/requests');
        const created = after.find(r => !before.some(old => old.request_id === r.request_id));
        if (created) setSuccess(`Request ${created.request_id} created. Your email was sent to the configured test inbox; the intended organizer has not been contacted in development mode.`);
      }
    } catch (e) { setError(`${(e as Error).message} If an action was submitted, it may still be running. No message was automatically resent.`); }
    finally { inFlight.current = false; setBusy(false); }
  }
  async function retryFormatting() {
    if (!job || inFlight.current) return;
    inFlight.current = true; setBusy(true); setError('');
    try {
      const queued = await api<Job>(`/jobs/${job.id}/presentation`, 'POST');
      inFlight.current = false;
      await run(undefined, queued);
    } catch (e) { setError((e as Error).message); }
    finally { inFlight.current = false; setBusy(false); }
  }
  useEffect(() => {
    if (started.current) return;
    started.current = true;
    async function initialize() {
      try {
        let saved: Saved | null = null;
        try { saved = JSON.parse(sessionStorage.getItem(key) || 'null'); } catch {}
        if (saved?.job && Array.isArray(saved.turns) && Array.isArray(saved.needs)) {
          state.current = saved; setJob(saved.job); setTurns(saved.turns); setNeeds(saved.needs);
          if (saved.job.status === 'processing' || !saved.turns.some(turn => turn.jobId === saved.job?.id)) await run(undefined, saved.job); else setBusy(false);
          return;
        }
        const profile = await api<{ needs: string[] }>('/profile');
        state.current.needs = profile.needs; setNeeds(profile.needs);
        await run();
      } catch (e) { setError((e as Error).message); setBusy(false); }
    }
    void initialize();
  }, [url]);
  const latestAgent = turns.reduce((last, turn, index) => turn.role === 'agent' ? index : last, -1);
  return <div className="workspace-shell">
    <nav className="workspace-nav" aria-label="Workspace"><button className="secondary-button" onClick={onBack} disabled={busy}>← Home</button><span className="brand-wordmark">Accessly<span aria-hidden="true"> ✦</span></span><button className="secondary-button" onClick={onDone} disabled={busy}>My Requests</button></nav>
    <header className="workspace-header"><span className="eyebrow">Your event companion</span><h1>Know before you go.</h1><p>Clear answers. Your needs. You decide what happens next.</p><a className="source-link" href={url} target="_blank" rel="noopener noreferrer">{url} ↗</a></header>
    <div className="conversation" aria-label="Conversation">
      {turns.map((turn, index) => turn.role === 'user' ? <div className="user-message" key={index}><span className="eyebrow">You</span><p>{turn.text}</p></div> : index === latestAgent ? <AgentResult key={index} result={turn.result} disabled={busy} onReply={text => void run(text)} onRetry={() => void retryFormatting()} /> : <div className="previous-response" key={index}><span className="eyebrow">Accessly</span><ReadableText text={turn.text}/></div>)}
    </div>
    {busy && <div className="loading-card" role="status"><span className="loading-orbit" aria-hidden="true"/><div><strong>{action === 'send' ? 'Accessly is processing your approved request…' : action === 'reply' ? 'Accessly is considering your reply…' : 'Accessly is checking the event…'}</strong><p>Checking official information can take a few minutes. You can leave this tab open.</p></div></div>}
    {error && <div className="error-card" role="alert"><strong>We couldn’t complete that action.</strong><p>{error}</p>{job?.status === 'processing' && <button className="secondary-button" disabled={busy} onClick={() => void run(undefined, job)}>Reconnect to current action</button>}{!job && <button className="secondary-button" onClick={onBack}>Return home</button>}</div>}
    {success && <div className="success-card" role="status"><strong>Request sent to test inbox</strong><p>{success}</p><button className="secondary-button" onClick={onDone}>View My Requests</button></div>}
    {job && <form className="result-card composer" onSubmit={e => { e.preventDefault(); if (answer.trim() && !busy) { const message = answer.trim(); setAnswer(''); void run(message); } }}>
      <label htmlFor="agent-answer">Continue the conversation</label><p className="helper-text">Ask a question, add a detail, or request a change. Sending requires your explicit approval of the exact draft.</p>
      <textarea id="agent-answer" placeholder="What would you like Accessly to know?" rows={3} value={answer} onChange={e => setAnswer(e.target.value)} maxLength={12000} disabled={busy} />
      <div className="button-row"><span className="helper-text">Your preferences stay in your profile.</span><button className="primary-button" disabled={busy || !answer.trim()}>Send reply ↑</button></div>
    </form>}
  </div>;
}

export function RequestsView({ onBack }: { onBack: () => void }) {
  const [requests, setRequests] = useState<TrackedRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [busyId, setBusyId] = useState('');
  const [error, setError] = useState('');
  const [response, setResponse] = useState<AgentPresentation>();
  const checking = useRef(false);
  async function refresh() { setRequests(await api<TrackedRequest[]>('/requests')); }
  useEffect(() => { refresh().catch(e => setError(e.message)).finally(() => setLoading(false)); }, []);
  async function check(id: string) {
    if (checking.current) return;
    checking.current = true; setBusyId(id); setError(''); setResponse(undefined);
    try {
      const result = await waitForJob(await api<Job>(`/requests/${id}/check`, 'POST'), () => {});
      if (result.status === 'failed') setError(result.response); else setResponse(result.result);
      await refresh();
    } catch (e) { setError((e as Error).message); }
    finally { checking.current = false; setBusyId(''); }
  }
  return <div className="workspace-shell"><nav className="workspace-nav"><button className="secondary-button" onClick={onBack} disabled={!!busyId}>← Home</button><span className="brand-wordmark">Accessly ✦</span></nav>
    <header className="workspace-header"><span className="eyebrow">Every request, in one place</span><h1>My Requests</h1><p>Follow each accommodation from request to confirmation.</p></header>
    {loading && <div className="loading-card" role="status">Loading your requests…</div>}
    {error && <div className="error-card" role="alert"><strong>Couldn’t load an update</strong><p>{error}</p><button className="secondary-button" disabled={!!busyId} onClick={() => { setError(''); refresh().catch(e => setError(e.message)); }}>Refresh requests</button></div>}
    {busyId && <p className="loading-card" role="status">Accessly is checking for updates to {busyId}…</p>}
    {response && <section className="result-card" role="status"><h2>Latest update</h2><ReadableText text={response.message} /></section>}
    {!loading && !error && !requests.length && <div className="result-card empty-state"><span aria-hidden="true">✉</span><h2>Your next event starts here.</h2><p>Once you approve a request and it’s sent, you can follow its progress here.</p><button className="primary-button" onClick={onBack}>Explore an event</button></div>}
    <div className="requests-grid">{requests.map(request => <article className="result-card" key={request.request_id}><div className="section-heading"><span className="eyebrow">{request.request_id}</span><StatusBadge status={request.status} /></div><h2>{request.event_name}</h2><div className="needs-list">{Object.entries(request.accommodations).map(([name, status]) => <div className="section-heading need-row" key={name}><h3>{name}</h3><StatusBadge status={status}/></div>)}</div><div className="button-row">{/^https?:\/\//i.test(request.event_url) && <a href={request.event_url} target="_blank" rel="noopener noreferrer">Event website ↗</a>}<button className="primary-button" disabled={!!busyId} onClick={() => void check(request.request_id)}>{busyId === request.request_id ? 'Checking…' : 'Check for Updates'}</button></div></article>)}</div>
  </div>;
}
