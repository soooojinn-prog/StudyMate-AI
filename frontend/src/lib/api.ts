/**
 * Backend API client. All HTTP calls to the backend go through this module
 * so that page components never hardcode URLs.
 */
const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendUrl(): string {
  return process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

export type HealthPayload = {
  status: string;
  app: string;
  version: string;
};

export type RubricItem = {
  point: string;
  weight: number;
  keywords: string[];
};

export type SessionState = {
  session_id: string;
  user_id: string;
  status: "awaiting_answer" | "graded" | "completed";
  topic: string | null;
  difficulty: number | null;
  target_weakness: boolean | null;
  question: string | null;
  model_answer: string | null;
  rubric: RubricItem[];
  ref_chunk_ids: string[];
  user_answer: string | null;
  score: number | null;
  rationale: string | null;
  feedback: string | null;
  missing_points: string[];
  questions_done: number;
  target_count: number;
  created_at: string;
};

async function _json<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, { cache: "no-store", ...init });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${detail}`);
  }
  return (await res.json()) as T;
}

export async function fetchHealth(): Promise<HealthPayload> {
  return _json<HealthPayload>(`${backendUrl()}/health`);
}

export async function createSession(opts?: {
  user_id?: string;
  target_count?: number;
  user_intent?: string;
}): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(opts ?? {}),
  });
}

export async function submitAnswer(
  sessionId: string,
  user_answer: string,
): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions/${sessionId}/answer`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ user_answer }),
  });
}

export async function getSession(sessionId: string): Promise<SessionState> {
  return _json<SessionState>(`${backendUrl()}/sessions/${sessionId}`);
}

export type WeakTopic = {
  topic: string;
  avg_score: number;
  sample_count: number;
};

export type TopicStat = {
  topic: string;
  answer_count: number;
  avg_score: number;
};

export type RecentAnswer = {
  session_id: string;
  topic: string;
  score: number;
  graded_at: string;
};

export type DashboardStats = {
  user_id: string;
  weak_topics: WeakTopic[];
  topic_stats: TopicStat[];
  recent_answers: RecentAnswer[];
  total_answers: number;
};

export async function fetchDashboardStats(userId: string): Promise<DashboardStats> {
  const url = new URL(`${backendUrl()}/dashboard/stats`);
  url.searchParams.set("user_id", userId);
  return _json<DashboardStats>(url.toString());
}
