import type { TrafficSample } from "../types.js";

export async function fetchFederalHighwaySample(
  apiKey: string | undefined,
): Promise<TrafficSample | null> {
  if (!apiKey) return null;
  return {
    source: "federal-highway",
    capturedAt: new Date().toISOString(),
    payload: { note: "Replace with real Federal Highway API call", hasKey: true },
  };
}
