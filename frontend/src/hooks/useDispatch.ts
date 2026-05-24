/**
 * useDispatch – Weeks 3-4 Oddle Autonomous Dispatcher hook
 */
import { useState, useCallback } from "react";

export interface DispatchRequest {
  incident_id: string;
  location: string;
  region: string;
  description: string;
}

export interface DispatchResult {
  incident_id: string;
  severity: Record<string, unknown>;
  impact: Record<string, unknown>;
  alternatives: Record<string, unknown>;
  decision: Record<string, unknown>;
  slack_payload: Record<string, unknown>;
}

export function useDispatch() {
  const [result, setResult] = useState<DispatchResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const analyseIncident = useCallback(async (req: DispatchRequest) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/dispatch/analyse", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req),
      });
      if (!response.ok) throw new Error(`API error ${response.status}`);
      const data: DispatchResult = await response.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { analyseIncident, result, loading, error };
}
