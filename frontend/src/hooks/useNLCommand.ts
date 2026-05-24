/**
 * useNLCommand – Week 1-2 Control Tower hook
 * Sends a natural-language logistics query to the backend NLP router
 * and returns the structured result for dashboard rendering.
 */
import { useState, useCallback } from "react";

export interface ParsedQuery {
  query_type: string;
  region: string;
  metric: string;
  time_frame: string;
  filters: Record<string, unknown>;
}

export interface NLCommandResult {
  query: ParsedQuery;
  raw_input: string;
  timestamp: Date;
}

export function useNLCommand() {
  const [result, setResult] = useState<NLCommandResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const executeCommand = useCallback(async (input: string) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/agent/parse-command", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input }),
      });

      if (!response.ok) {
        throw new Error(`API error ${response.status}: ${await response.text()}`);
      }

      const { query, raw_input } = await response.json();
      setResult({ query, raw_input, timestamp: new Date() });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, []);

  return { executeCommand, result, loading, error };
}
