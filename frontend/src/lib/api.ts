/**
 * PitchPilot — typed API client.
 *
 * All backend calls go through these functions.
 * The Vite dev proxy forwards /api/* → http://localhost:8000.
 */

import type {
  FindingsResponse,
  ReadinessReport,
  SessionStartResponse,
  SessionStatusResponse,
  TimelineResponse,
} from "@/types";

const BASE = "/api";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  // 202 = still processing — let callers handle as a non-error
  if (res.status === 202) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? "Processing");
  }
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body?.detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  /**
   * Upload a rehearsal video (and optional policy docs) to start analysis.
   * Returns a session_id to poll with.
   */
  startSession(
    video: File,
    policyDocs: File[] = [],
    personas: string[] = ["Skeptical Investor", "Technical Reviewer", "Compliance Officer"]
  ): Promise<SessionStartResponse> {
    const form = new FormData();
    form.append("video", video);
    for (const doc of policyDocs) {
      form.append("policy_docs", doc);
    }
    form.append("personas", personas.join(","));
    return request<SessionStartResponse>(`${BASE}/session/start`, {
      method: "POST",
      body: form,
    });
  },

  /** Poll processing progress. Throws on 202 (still running) — catch and ignore. */
  getStatus(sessionId: string): Promise<SessionStatusResponse> {
    return request<SessionStatusResponse>(`${BASE}/session/${sessionId}/status`);
  },

  /** Full readiness report — only resolves when status === 'complete'. */
  getReport(sessionId: string): Promise<ReadinessReport> {
    return request<ReadinessReport>(`${BASE}/session/${sessionId}/report`);
  },

  /** Timeline annotations for the timeline strip. */
  getTimeline(sessionId: string): Promise<TimelineResponse> {
    return request<TimelineResponse>(`${BASE}/session/${sessionId}/timeline`);
  },

  /** All agent findings and persona questions. */
  getFindings(sessionId: string): Promise<FindingsResponse> {
    return request<FindingsResponse>(`${BASE}/session/${sessionId}/findings`);
  },
};

/**
 * Returns the WebSocket URL for a live session.
 * In development (Vite proxy) we connect directly to the backend port
 * because the Vite dev proxy only forwards HTTP, not WebSocket upgrades.
 */
export function getLiveSessionWsUrl(): string {
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  // In dev mode the backend is always on :8000
  const host =
    import.meta.env.DEV
      ? `${window.location.hostname}:8000`
      : window.location.host;
  return `${proto}//${host}/api/session/live`;
}
