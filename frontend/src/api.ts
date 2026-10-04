import type { AgentPresentation } from "./presentation";
export type Job = { id: string; session_id: string; status: string; response: string; result?: AgentPresentation };
export type TrackedRequest = { request_id: string; event_name: string; event_url: string; status: string; accommodations: Record<string, string> };
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
function visitorToken(): string {
  const key = 'accessly:visitor:v1';
  let token = localStorage.getItem(key);
  if (!token || !/^[0-9a-f]{64}$/.test(token)) {
    token = Array.from(crypto.getRandomValues(new Uint8Array(32)), byte => byte.toString(16).padStart(2, '0')).join('');
    localStorage.setItem(key, token);
  }
  return token;
}
export async function api<T>(path: string, method = "GET", body?: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { method, headers: { Authorization: `Bearer ${visitorToken()}`, ...(body === undefined ? {} : { "Content-Type": "application/json" }) }, body: body === undefined ? undefined : JSON.stringify(body) });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new Error(typeof error?.detail === "string" ? error.detail : `Request failed (${response.status}).`);
  }
  return response.json();
}
export async function waitForJob(job: Job, update: (job: Job) => void): Promise<Job> {
  update(job);
  while (job.status === "processing") {
    await new Promise(resolve => setTimeout(resolve, 1200));
    job = await api<Job>(`/jobs/${job.id}`);
    update(job);
  }
  return job;
}
