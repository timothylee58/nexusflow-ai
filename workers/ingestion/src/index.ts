import "dotenv/config";
import { fetchFederalHighwaySample } from "./fetchers/federal-highway.js";
import { fetchLdpSample } from "./fetchers/ldp.js";
import { publishIngestionEvent } from "./redis-producer.js";

const CHANNEL = process.env.INGESTION_REDIS_CHANNEL ?? "nexusflow:traffic";
const INTERVAL_MS = Number(process.env.INGESTION_INTERVAL_MS ?? "60000");

async function tick() {
  const apiKey = process.env.TRAFFIC_API_KEY;
  const fh = await fetchFederalHighwaySample(apiKey);
  const ldp = await fetchLdpSample(apiKey);
  const batch = [fh, ldp].filter(Boolean);

  if (batch.length === 0) {
    const heartbeat = {
      source: "ingestion",
      capturedAt: new Date().toISOString(),
      payload: { note: "No external keys configured; heartbeat only" },
    };
    await publishIngestionEvent(CHANNEL, heartbeat);
    console.log("[ingestion] heartbeat published");
    return;
  }

  for (const sample of batch) {
    await publishIngestionEvent(CHANNEL, sample);
    console.log("[ingestion] published", sample?.source);
  }
}

async function main() {
  console.log(`[ingestion] starting, interval ${INTERVAL_MS}ms, channel ${CHANNEL}`);
  await tick();
  setInterval(() => {
    tick().catch((err) => console.error("[ingestion] tick error", err));
  }, INTERVAL_MS);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
