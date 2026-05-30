/**
 * Backend API client. All HTTP calls to the backend go through this module
 * so that page components never hardcode URLs.
 */
const DEFAULT_BACKEND_URL = "http://localhost:8000";

function backendUrl(): string {
  // BACKEND_URL is set in .env.local for dev. Falls back to localhost.
  return process.env.BACKEND_URL ?? DEFAULT_BACKEND_URL;
}

export type HealthPayload = {
  status: string;
  app: string;
  version: string;
};

export async function fetchHealth(): Promise<HealthPayload> {
  const res = await fetch(`${backendUrl()}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Backend /health responded ${res.status}`);
  }
  return (await res.json()) as HealthPayload;
}
