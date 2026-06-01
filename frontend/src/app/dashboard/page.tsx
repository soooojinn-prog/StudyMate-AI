import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { fetchDashboardStats, type DashboardStats } from "@/lib/api";

export const dynamic = "force-dynamic";

const SCORE_GOOD = 0.7;
const SCORE_MID = 0.4;

function scoreClass(score: number): string {
  if (score >= SCORE_GOOD) return "font-display text-[24px] text-cyan";
  if (score >= SCORE_MID) return "font-display text-[24px] text-amber";
  return "font-display text-[24px] text-danger";
}

function formatGradedAt(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ");
}

export default async function DashboardPage() {
  let stats: DashboardStats | null = null;
  let error: string | null = null;
  try {
    stats = await fetchDashboardStats("local-user");
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  if (error || !stats) {
    return (
      <main className="mx-auto max-w-4xl p-10">
        <div className="border border-danger/40 bg-danger/5 p-6">
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-danger">
            {"dashboard_load_failed"}
          </p>
          <pre className="mt-3 whitespace-pre-wrap text-sm text-ink-mid">{error}</pre>
        </div>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-5xl px-10 py-12 bg-blueprint-grid bg-[length:36px_36px]">
      <header className="flex items-baseline justify-between border-y border-panel-line py-3 mb-10 font-mono text-[11px] uppercase tracking-[0.22em] text-ink-soft">
        <span>
          <span className="text-cyan">●</span> Dashboard · {stats.user_id}
        </span>
        <span>
          {stats.total_answers} answers · last 30 days
        </span>
      </header>

      <section className="mb-12">
        <Badge tone="amber" className="mb-4">
          · Weakness Top-3 · 가중평균 낮은 주제
        </Badge>
        {stats.weak_topics.length === 0 ? (
          <p className="text-ink-mid">
            데이터가 충분하지 않습니다 (한 주제당 ≥3개 답변 필요).
          </p>
        ) : (
          <ol className="grid gap-3">
            {stats.weak_topics.map((w, i) => (
              <Card
                key={w.topic}
                className="grid grid-cols-[60px_1fr_auto] items-center gap-4"
              >
                <span className="font-display italic text-[40px] leading-none text-amber">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <div>
                  <p className="text-[20px] font-medium">{w.topic}</p>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                    {w.sample_count} answers
                  </p>
                </div>
                <span className="font-display text-[36px] text-amber">
                  {w.avg_score.toFixed(2)}
                </span>
              </Card>
            ))}
          </ol>
        )}
      </section>

      <section className="mb-12">
        <Badge tone="cyan" className="mb-4">
          · Topic Stats · 주제별 평균
        </Badge>
        {stats.topic_stats.length === 0 ? (
          <p className="text-ink-mid">아직 풀이 이력이 없습니다.</p>
        ) : (
          <ol className="border-t border-panel-line">
            {stats.topic_stats.map((t) => (
              <li
                key={t.topic}
                className="grid grid-cols-[1fr_auto_auto] items-center gap-6 py-3 border-b border-panel-line"
              >
                <span className="text-[16.5px]">{t.topic}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
                  {t.answer_count} answers
                </span>
                <span className="font-display text-[20px] text-cyan">
                  {t.avg_score.toFixed(2)}
                </span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section>
        <Badge tone="magenta" className="mb-4">
          · Recent · 최근 답변 10건
        </Badge>
        {stats.recent_answers.length === 0 ? (
          <p className="text-ink-mid">최근 답변이 없습니다.</p>
        ) : (
          <ol className="border-t border-panel-line">
            {stats.recent_answers.map((r, i) => (
              <li
                key={`${r.session_id}-${i}`}
                className="grid grid-cols-[120px_1fr_auto_auto] items-center gap-4 py-3 border-b border-panel-line"
              >
                <span className="font-mono text-[10.5px] tracking-[0.18em] uppercase text-ink-soft">
                  {formatGradedAt(r.graded_at)}
                </span>
                <span className="text-ink">{r.topic}</span>
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-ink-mid">
                  {r.session_id.slice(0, 8)}
                </span>
                <span className={scoreClass(r.score)}>{r.score.toFixed(2)}</span>
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  );
}
