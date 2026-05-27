import { type NextRequest } from "next/server";

const BACKEND =
  process.env.INTERNAL_API_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8000";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function GET(req: NextRequest) {
  const controller = new AbortController();
  req.signal.addEventListener("abort", () => controller.abort());

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND}/sse/metrics`, {
      signal: controller.signal,
      headers: { Accept: "text/event-stream", "Cache-Control": "no-cache" },
    });
  } catch {
    return new Response("upstream unavailable", { status: 502 });
  }

  if (!upstream.body) {
    return new Response("no body from upstream", { status: 502 });
  }

  return new Response(upstream.body, {
    status: 200,
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
