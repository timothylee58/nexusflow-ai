/**
 * useModelRouter – Weeks 7-8 cost-optimisation hook
 */
import { useState, useCallback, useEffect } from "react";

export interface RouteResult {
  query: string;
  complexity: string;
  model_used: string;
  response: string;
  tokens_used: number;
  cost_usd: number;
  timestamp: string;
}

export interface RouterStats {
  total_queries: number;
  breakdown: { haiku: number; sonnet: number; opus: number };
  total_cost_usd: number;
  hypothetical_all_opus_usd: number;
  savings_usd: number;
  savings_pct: number;
}

export function useModelRouter() {
  const [routeResult, setRouteResult] = useState<RouteResult | null>(null);
  const [stats, setStats] = useState<RouterStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const routeQuery = useCallback(
    async (query: string, context: Record<string, unknown> = {}) => {
      setLoading(true);
      setError(null);
      try {
        const response = await fetch("/api/model/route", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query, context }),
        });
        if (!response.ok) throw new Error(`API error ${response.status}`);
        const data: RouteResult = await response.json();
        setRouteResult(data);
        await refreshStats();
      } catch (err) {
        setError(err instanceof Error ? err.message : "Unknown error");
      } finally {
        setLoading(false);
      }
    },
    []
  );

  const refreshStats = useCallback(async () => {
    try {
      const response = await fetch("/api/model/stats");
      if (response.ok) {
        const data: RouterStats = await response.json();
        setStats(data);
      }
    } catch {
      // stats refresh failure is non-critical
    }
  }, []);

  useEffect(() => {
    refreshStats();
  }, [refreshStats]);

  return { routeQuery, routeResult, stats, loading, error };
}
