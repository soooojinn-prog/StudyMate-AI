"use client";

import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { submitAnswer, type SessionState } from "@/lib/api";

export function SessionView({ initial }: { initial: SessionState }) {
  const [state, setState] = useState<SessionState>(initial);
  const [answer, setAnswer] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isGraded = state.status === "graded" && state.score !== null;

  async function onSubmit() {
    if (!answer.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const next = await submitAnswer(state.session_id, answer);
      setState(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="mx-auto max-w-4xl px-10 py-12 bg-blueprint-grid bg-[length:36px_36px]">
      {/* masthead */}
      <header className="flex items-baseline justify-between border-y border-panel-line py-3 mb-10 font-mono text-[11px] uppercase tracking-[0.22em] text-ink-soft">
        <span>
          <span className="text-cyan">●</span> Live · StudyMate
        </span>
        <span>Session {state.session_id.slice(0, 8)} · {state.target_count} 문제</span>
      </header>

      {/* question */}
      <section className="mb-10">
        <Badge tone="cyan" className="mb-4">
          ● Question Generated · k=5 retrieval
        </Badge>
        <h1 className="font-display italic font-medium text-[clamp(72px,10vw,116px)] leading-[0.92] tracking-tight">
          {String(state.questions_done + 1).padStart(2, "0")}
          <span className="text-ink-soft mx-2">/</span>
          <span className="text-ink-soft">{String(state.target_count).padStart(2, "0")}</span>
        </h1>
        <p className="mt-4 text-[24px] leading-snug font-medium max-w-[36ch]">
          {state.question}
        </p>
        {state.topic && (
          <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-mid">
            Topic · {state.topic} · 난이도 {state.difficulty ?? "?"}
          </p>
        )}
      </section>

      {/* answer form (visible until graded) */}
      {!isGraded && (
        <section className="mb-10">
          <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan mb-3">
            {"// answer.input"}
          </p>
          <Textarea
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            placeholder="여기에 답안을 작성하세요…"
            disabled={submitting}
          />
          <div className="mt-4 flex items-center gap-4">
            <Button onClick={onSubmit} disabled={submitting || !answer.trim()}>
              {submitting ? "채점 중…" : "채점 받기 →"}
            </Button>
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-soft">
              {answer.length} chars
            </span>
          </div>
          {error && (
            <p className="mt-4 font-mono text-[11px] text-danger tracking-[0.18em] uppercase">
              error · {error}
            </p>
          )}
        </section>
      )}

      {/* grading result */}
      {isGraded && (
        <>
          <section className="mb-10">
            <Badge tone="amber" className="mb-4">
              · Grading · Sonnet 4.6
            </Badge>
            <Card>
              <p className="font-mono text-[10px] uppercase tracking-[0.28em] text-amber mb-3">
                Score · partial
              </p>
              <div className="flex items-baseline gap-3">
                <span className="font-display text-[100px] leading-[0.85] font-medium tracking-tight">
                  {state.score?.toFixed(2)}
                </span>
                <span className="font-display italic text-[22px] text-ink-soft">/1.00</span>
              </div>
              <ol className="mt-6 border-t border-panel-line">
                {state.rubric.map((r, i) => {
                  const matched = !state.missing_points.includes(r.keywords[0] ?? "");
                  return (
                    <li
                      key={i}
                      className="grid grid-cols-[40px_1fr_auto] items-center gap-4 py-3.5 border-b border-panel-line text-[16.5px]"
                    >
                      <span className="font-mono text-[11px] text-ink-soft tracking-[0.18em]">
                        R{String(i + 1).padStart(2, "0")}
                      </span>
                      <span className="text-ink">{r.point}</span>
                      <Badge tone={matched ? "cyan" : "amber"}>
                        {matched ? "✓ match" : "✕ missing"}
                      </Badge>
                    </li>
                  );
                })}
              </ol>
            </Card>
          </section>

          {state.feedback && (
            <section className="mb-10">
              <Badge tone="magenta" className="mb-4">
                · Reinforcement note
              </Badge>
              <div className="border border-dashed border-magenta bg-magenta/5 p-6">
                <p className="text-[18px] leading-relaxed text-ink">{state.feedback}</p>
                {state.missing_points.length > 0 && (
                  <p className="mt-4 font-mono text-[11px] uppercase tracking-[0.18em] text-amber">
                    Missing → {state.missing_points.join(" · ")}
                  </p>
                )}
              </div>
            </section>
          )}

          <div className="mt-12 flex gap-3 border-t border-panel-line pt-6">
            <Button onClick={() => window.location.reload()}>다음 문제 →</Button>
            <Button variant="ghost" onClick={() => window.location.reload()}>
              재시도
            </Button>
          </div>
        </>
      )}
    </main>
  );
}
