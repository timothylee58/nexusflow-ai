import type { TrafficSample } from "../types.js";

const REGIONS = ["MY", "SG", "HK", "TW"] as const;
type Region = (typeof REGIONS)[number];

// Baseline congestion levels per region (realistic SE/EA Asia logistics)
const BASE: Record<Region, { congestion: number; deliveryH: number; activeK: number }> = {
  MY: { congestion: 68, deliveryH: 3.2, activeK: 1.847 },
  SG: { congestion: 55, deliveryH: 1.8, activeK: 3.201 },
  HK: { congestion: 72, deliveryH: 2.1, activeK: 2.956 },
  TW: { congestion: 61, deliveryH: 2.6, activeK: 1.623 },
};

function jitter(base: number, pct: number): number {
  return +(base + (Math.random() * 2 - 1) * base * pct).toFixed(1);
}

export function generateSyntheticSample(region: Region): TrafficSample {
  const b = BASE[region];
  const congestion = Math.min(100, Math.max(0, Math.round(jitter(b.congestion, 0.15))));
  const activeIncidents =
    congestion > 80
      ? Math.floor(Math.random() * 5) + 1
      : congestion > 65
        ? Math.floor(Math.random() * 3)
        : 0;

  return {
    source: `synthetic-${region}`,
    capturedAt: new Date().toISOString(),
    payload: {
      region,
      congestion,
      avg_delivery_time: jitter(b.deliveryH, 0.1),
      active_deliveries: Math.round(jitter(b.activeK * 1000, 0.05)),
      active_incidents: activeIncidents,
    },
  };
}

export function fetchAllSyntheticSamples(): TrafficSample[] {
  return REGIONS.map(generateSyntheticSample);
}
