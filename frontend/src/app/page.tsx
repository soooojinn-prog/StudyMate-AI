import Link from "next/link";

import { Button } from "@/components/ui/button";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl px-10 py-20">
      <p className="font-mono text-[11px] uppercase tracking-[0.22em] text-cyan mb-6">
        StudyMate — vol.01 iss.04
      </p>
      <h1 className="font-display italic text-[clamp(64px,9vw,108px)] leading-[0.95] tracking-tight">
        Multi-agent<br />learning, fenced
      </h1>
      <p className="mt-6 text-[19px] text-ink-mid max-w-[42ch] leading-relaxed">
        멀티 에이전트 기반 학습 시스템. 정보처리기사 실기 도메인. LangGraph
        + RAG로 학습자 답안을 의미 기반으로 채점하고 근거 청크와 함께
        보강 가이드를 제공합니다.
      </p>
      <div className="mt-10 flex gap-3">
        <Button asChild>
          <Link href="/study">학습 시작 →</Link>
        </Button>
        <Button variant="ghost" asChild>
          <Link href="/health">시스템 상태</Link>
        </Button>
      </div>
    </main>
  );
}
