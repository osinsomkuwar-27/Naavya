/**
 * frontend/src/lib/api.ts
 *
 * Typed HTTP client for the Naavya FastAPI backend.
 *
 * All fetch calls go through here — never call fetch() directly in
 * components. This keeps the base URL, headers, and error handling in
 * one place so they can be changed without touching every route file.
 *
 * Base URL resolution (in priority order):
 *   1. VITE_API_URL env var  (set in frontend/.env for local dev)
 *   2. /api prefix           (for production reverse-proxy deploys)
 *   3. http://localhost:8000 (ultimate fallback)
 */

const API_BASE: string =
  (import.meta.env.VITE_API_URL as string | undefined) ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Shared fetch wrapper
// ---------------------------------------------------------------------------

async function apiFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    ...init,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore parse errors */
    }
    throw new Error(detail);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Endpoint: GET /health
// ---------------------------------------------------------------------------

export interface HealthResponse {
  status: string;
  service: string;
}

export async function healthCheck(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>("/health");
}

// ---------------------------------------------------------------------------
// Endpoint: POST /assess
// ---------------------------------------------------------------------------

export interface AssessRequest {
  transcript: string;
  conversation_id?: string;
  language?: string;
  source?: string;
}

export interface AssessResponse {
  conversation_id: string;
  status: string;
  risk_level: "reassure" | "contact_asha" | "refer_now" | null;
  recommendation: string | null;
  next_steps: string[];
  pending_question: string | null;
  clear_signs: Record<string, string>;
  vague_signs: string[];
  audit_flags: string[];
  source?: string;
}

export async function submitAssessment(
  req: AssessRequest,
): Promise<AssessResponse> {
  return apiFetch<AssessResponse>("/assess", {
    method: "POST",
    body: JSON.stringify(req),
  });
}

// ---------------------------------------------------------------------------
// Endpoint: POST /assess/voice
// ---------------------------------------------------------------------------

export async function submitVoiceAssessment(
  audioBlob: Blob,
  conversationId?: string,
  language = "en",
  source = "web_mic",
): Promise<AssessResponse> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.ogg");
  if (conversationId) formData.append("conversation_id", conversationId);
  formData.append("language", language);
  formData.append("source", source);

  const url = `${API_BASE}/assess/voice`;
  const res = await fetch(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = (await res.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      /* ignore parse error */
    }
    throw new Error(detail);
  }

  return res.json() as Promise<AssessResponse>;
}

// ---------------------------------------------------------------------------
// Map backend risk_level → frontend Risk type
// ---------------------------------------------------------------------------

export function mapRiskLevel(
  risk_level: AssessResponse["risk_level"],
): "low" | "medium" | "high" {
  switch (risk_level) {
    case "refer_now":
      return "high";
    case "contact_asha":
      return "medium";
    case "reassure":
    default:
      return "low";
  }
}

