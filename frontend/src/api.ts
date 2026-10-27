import { firebaseEnabled, firebaseToken, firebaseSignOut } from "./firebase";
import type { AgentPresentation } from "./presentation";
export type Job = { id: string; session_id: string; status: string; response: string; result?: AgentPresentation };
export type TrackedRequest = { request_id: string; event_name: string; event_url: string; status: string; accommodations: Record<string, string> };
const API_BASE = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '');
const TOKEN_KEY = 'accessly:auth:v1';

export function clearConversations(): void {
  for (const key of Object.keys(sessionStorage)) {
    if (key.startsWith('accessly:conversation:v2:')) sessionStorage.removeItem(key);
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function endSession(): void {
  if (firebaseEnabled) void firebaseSignOut().catch(() => undefined);
  localStorage.removeItem(TOKEN_KEY);
  clearConversations();
}

export function setAccessToken(token: string): void {
  // Conversations in the existing workspace are keyed by URL. Never reuse
  // that cache across login/account changes.
  clearConversations();
  localStorage.setItem(TOKEN_KEY, token);
}

export async function api<T>(path: string, method = "GET", body?: unknown, options: { signal?: AbortSignal; keepSession?: boolean } = {}): Promise<T> {
  const publicAuth = path.startsWith('/auth/');
  let token: string | null;
  try { token = firebaseEnabled ? (publicAuth ? null : await firebaseToken()) : getAccessToken(); }
  catch {
    if (!options.keepSession) {
      endSession();
      window.dispatchEvent(new Event('accessly:auth-required'));
    }
    throw new Error('Your session expired. Log in to continue.');
  }
  if (!publicAuth && !token) {
    if (!options.keepSession) window.dispatchEvent(new Event('accessly:auth-required'));
    throw new Error('Log in to continue.');
  }
  const response = await fetch(`${API_BASE}${path}`, { method, headers: {
    ...(!publicAuth && token ? { Authorization: `Bearer ${token}` } : {}),
    ...(body === undefined ? {} : { "Content-Type": "application/json" }),
  }, body: body === undefined ? undefined : JSON.stringify(body), signal: options.signal });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    if (response.status === 401 && !publicAuth && !options.keepSession) {
      endSession();
      window.dispatchEvent(new Event('accessly:auth-required'));
    }
    throw new Error(typeof error?.detail === "string" ? error.detail : `Request failed (${response.status}).`);
  }
  if (response.status === 204) return undefined as T;
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
