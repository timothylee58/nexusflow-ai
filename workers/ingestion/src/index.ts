import "dotenv/config";
import { fetchFederalHighwaySample } from "./fetchers/federal-highway.js";
import { fetchLdpSample } from "./fetchers/ldp.js";
import { fetchAllSyntheticSamples } from "./fetchers/synthetic.js";
import { publishIngestionEvent } from "./redis-producer.js";

const CHANNEL = process.env.INGESTION_REDIS_CHANNEL ?? "nexusflow:traffic";
const INTERVAL_MS = Number(process.env.INGESTION_INTERVAL_MS ?? "15000");

async function tick() {
  const apiKey = process.env.TRAFFIC_API_KEY;

  // Try live API fetchers first; fall back to synthetic data (always available)
  const fh = await fetchFederalHighwaySample(apiKey);
  const ldp = await fetchLdpSample(apiKey);
  const liveData = [fh, ldp].filter(Boolean);

  const samples = liveData.length > 0 ? liveData : fetchAllSyntheticSamples();

  for (const sample of samples) {
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
