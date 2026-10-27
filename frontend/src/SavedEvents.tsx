import { useEffect, useState } from "react";
import { api } from "./api";
import { firebaseEnabled } from "./firebase";
import { RequestsView } from "./AgentWorkspace";
import AgentResult, { ReadableText, StatusBadge } from "./AgentResult";
import type { AgentPresentation } from "./presentation";

type Summary = { id: string; event_name: string; event_url: string; status: string; saved_at: string };
type Snapshot = Summary & { result: AgentPresentation; needs: string[]; response: string; conversation: { role: "user" | "agent"; text: string }[] };

export default function PreviousEvents({ onBack }: { onBack: () => void }) {
  const [events, setEvents] = useState<Summary[]>([]);
  const [selected, setSelected] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState(firebaseEnabled);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState("");
  async function load() {
    setLoading(true); setError("");
    try { setEvents(await api<Summary[]>("/saved-events")); }
    catch (failure) { setError((failure as Error).message); }
    finally { setLoading(false); }
  }
  useEffect(() => { if (firebaseEnabled) void load(); }, []);
  async function open(id: string) {
    if (opening) return;
    setOpening(true); setError("");
    try { setSelected(await api<Snapshot>(`/saved-events/${id}`)); }
    catch (failure) { setError((failure as Error).message); }
    finally { setOpening(false); }
  }
  if (selected) {
    const latest = selected.conversation.reduce((last, turn, i) => turn.role === "agent" ? i : last, -1);
    return <div className="workspace-shell">
      <nav className="workspace-nav"><button className="secondary-button" onClick={() => setSelected(null)}>← Previous Events</button><span className="brand-wordmark">Accessly ✦</span></nav>
      <header className="workspace-header"><span className="eyebrow">Saved event</span><h1>{selected.event_name}</h1><StatusBadge status={selected.status}/><p><a className="source-link" href={selected.event_url} target="_blank" rel="noopener noreferrer">{selected.event_url} ↗</a></p></header>
      <div className="conversation" aria-label="Saved conversation">
        {selected.conversation.map((turn, i) => turn.role === "user" ? <div className="user-message" key={i}><span className="eyebrow">You</span><p>{turn.text}</p></div> : i === latest ? <AgentResult key={i} result={selected.result} disabled/> : <div className="previous-response" key={i}><span className="eyebrow">Accessly</span><ReadableText text={turn.text}/></div>)}
        {latest < 0 && <AgentResult result={selected.result} disabled/>}
      </div>
    </div>;
  }
  const saved = firebaseEnabled ? <section aria-label="Saved events" style={{ marginBottom: 24 }}>
    <h2>Saved Events</h2>
    {loading && <p className="loading-card" role="status">Loading saved events…</p>}
    {error && <div className="error-card" role="alert"><p>{error}</p><button className="secondary-button" onClick={() => void load()}>Retry</button></div>}
    {!loading && !events.length && !error && <p className="helper-text">Events you save after analysis will appear here.</p>}
    <div className="requests-grid">{events.map(event => <article className="result-card" key={event.id}><div className="section-heading"><span className="eyebrow">Saved event</span><StatusBadge status={event.status}/></div><h2>{event.event_name}</h2><p className="helper-text">{event.event_url}</p><button className="primary-button" disabled={opening} onClick={() => void open(event.id)}>{opening ? "Opening…" : "Open Saved Event"}</button></article>)}</div>
  </section> : undefined;
  return <RequestsView onBack={onBack} savedEvents={saved}/>;
}
