import { SessionView } from "./session-view";
import { createSession } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function StudyPage() {
  let initial = null;
  let error: string | null = null;
  try {
    initial = await createSession({ user_id: "local-user", target_count: 5 });
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error) {
    return (
      <main className="mx-auto max-w-3xl p-10">
        <div className="border border-danger/40 bg-danger/5 p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-danger">
            session_start_failed
          </p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-ink-mid">{error}</pre>
        </div>
      </main>
    );
  }

  if (!initial) return null;
  return <SessionView initial={initial} />;
}
