import type { TrafficSample } from "../types.js";

export async function fetchLdpSample(apiKey: string | undefined): Promise<TrafficSample | null> {
  if (!apiKey) return null;
  return {
    source: "ldp",
    capturedAt: new Date().toISOString(),
    payload: { note: "Replace with real LDP API call", hasKey: true },
  };
}
