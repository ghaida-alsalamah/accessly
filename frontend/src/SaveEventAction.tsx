import { useEffect, useRef, useState } from "react";
import { api, type Job } from "./api";
import { firebaseEnabled } from "./firebase";

export default function SaveEventAction({ job, turns, busy, onBusy, onSaved }: {
  job: Job | null; turns: { role: "user" | "agent"; text: string }[];
  busy: boolean; onBusy: (value: boolean) => void; onSaved: () => void;
}) {
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState("");
  const inFlight = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current); }, []);
  if (!firebaseEnabled || busy || job?.status !== "completed" || job.result?.presentation_status !== "ready") return null;
  async function save() {
    if (!job || inFlight.current) return;
    inFlight.current = true; setSaving(true); setError(""); onBusy(true);
    try {
      await api("/saved-events", "POST", { job_id: job.id, conversation: turns.map(({ role, text }) => ({ role, text })) });
      setSaved(true);
      timer.current = setTimeout(onSaved, 1800);
    } catch (failure) {
      setError((failure as Error).message); inFlight.current = false; onBusy(false);
    } finally { setSaving(false); }
  }
  return <div style={{ marginTop: 20 }}>
    <div className="button-row"><button type="button" className="primary-button" disabled={saving || saved} onClick={() => void save()}>{saving ? "Saving…" : saved ? "Saved" : "Save Event"}</button></div>
    {error && <p className="error-card" role="alert">{error}</p>}
    {saved && <div role="status" style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 100, padding: "12px 20px", borderRadius: 12, background: "#e7f3e8", color: "#21523a", border: "1px solid #cee3d0", boxShadow: "0 4px 18px #29242112", fontSize: 14 }}>Event saved successfully.</div>}
  </div>;
}
