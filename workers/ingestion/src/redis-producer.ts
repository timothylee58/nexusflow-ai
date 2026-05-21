import Redis from "ioredis";

const UPSTASH_REST = process.env.UPSTASH_REDIS_REST_URL;
const UPSTASH_TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN;
const REDIS_URL = process.env.REDIS_URL;

let client: Redis | null = null;

function getRedis(): Redis | null {
  if (!REDIS_URL) return null;
  if (!client) client = new Redis(REDIS_URL, { maxRetriesPerRequest: 2 });
  return client;
}

export async function publishIngestionEvent(channel: string, body: unknown): Promise<void> {
  const payload = JSON.stringify(body);

  const redis = getRedis();
  if (redis) {
    await redis.publish(channel, payload);
    return;
  }

  if (UPSTASH_REST && UPSTASH_TOKEN) {
    const url = UPSTASH_REST.replace(/\/$/, "");
    const res = await fetch(url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${UPSTASH_TOKEN}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(["PUBLISH", channel, payload]),
    });
    if (!res.ok) {
      throw new Error(`Upstash publish failed: ${res.status} ${await res.text()}`);
    }
    return;
  }

  console.warn("[ingestion] No REDIS_URL or Upstash REST config — event dropped (dev mode).");
}
