import { fetchHealth } from "@/lib/api";

export const dynamic = "force-dynamic";

export default async function HealthPage() {
  let payload: Awaited<ReturnType<typeof fetchHealth>> | null = null;
  let error: string | null = null;

  try {
    payload = await fetchHealth();
  } catch (err) {
    error = err instanceof Error ? err.message : String(err);
  }

  return (
    <main className="mx-auto max-w-2xl p-8">
      <h1 className="text-2xl font-bold">시스템 상태</h1>

      {error && (
        <div className="mt-4 rounded border border-red-300 bg-red-50 p-4 text-red-800">
          <p className="font-semibold">백엔드 호출 실패</p>
          <pre className="mt-2 whitespace-pre-wrap text-sm">{error}</pre>
        </div>
      )}

      {payload && (
        <dl className="mt-4 grid grid-cols-2 gap-y-2 rounded border border-gray-200 bg-gray-50 p-4">
          <dt className="font-semibold">Status</dt>
          <dd>{payload.status}</dd>
          <dt className="font-semibold">App</dt>
          <dd>{payload.app}</dd>
          <dt className="font-semibold">Version</dt>
          <dd>{payload.version}</dd>
        </dl>
      )}
    </main>
  );
}
