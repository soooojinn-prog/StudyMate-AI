import Link from "next/link";

export default function HomePage() {
  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-3xl font-bold">StudyMate AI</h1>
      <p className="mt-2 text-gray-600">
        멀티 에이전트 기반 학습 시스템 (정보처리기사 실기 V1).
      </p>
      <Link
        href="/health"
        className="mt-6 inline-block rounded bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
      >
        시스템 상태 확인 →
      </Link>
    </main>
  );
}
