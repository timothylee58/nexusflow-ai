const apiUrl =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export default async function Home() {
  let health: { status?: string } = {};
  try {
    const res = await fetch(`${apiUrl}/health`, { next: { revalidate: 0 } });
    if (res.ok) health = await res.json();
  } catch {
    health = { status: "unreachable" };
  }

  return (
    <main className="mx-auto flex max-w-3xl flex-col gap-6 px-6 py-16">
      <h1 className="text-3xl font-semibold tracking-tight">NexusFlow</h1>
      <p className="text-zinc-400">
        API health:{" "}
        <code className="rounded bg-zinc-800 px-2 py-0.5 text-sm text-emerald-400">
          {health.status ?? "unknown"}
        </code>{" "}
        <span className="text-zinc-500">({apiUrl})</span>
      </p>
      <a
        href="/dashboard"
        className="inline-flex w-fit rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-500"
      >
        Open Control Tower →
      </a>
    </main>
  );
}
