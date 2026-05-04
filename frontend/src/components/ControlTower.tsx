/**
 * ControlTower – Week 1-2 NL Command Interface
 * Allows operators to type natural-language queries; shows parsed JSON result.
 */
import React, { useState } from "react";
import { useNLCommand } from "../hooks/useNLCommand";

const EXAMPLES = [
  "Show me delivery bottlenecks in KL right now",
  "Cost analysis for Singapore this week",
  "Driver availability in Hong Kong today",
  "Route optimisation for Taiwan deliveries",
];

const REGION_FLAG: Record<string, string> = {
  MY: "🇲🇾",
  SG: "🇸🇬",
  HK: "🇭🇰",
  TW: "🇹🇼",
};

export default function ControlTower() {
  const [input, setInput] = useState("");
  const { executeCommand, result, loading, error } = useNLCommand();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (input.trim()) executeCommand(input.trim());
  };

  return (
    <section style={styles.section}>
      <h2 style={styles.heading}>🗼 Control Tower – NL Command Interface</h2>
      <p style={styles.sub}>
        Type a natural-language logistics query. AI parses it into a structured
        command.
      </p>

      <form onSubmit={handleSubmit} style={styles.form}>
        <input
          style={styles.input}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="e.g. Show me delivery bottlenecks in KL right now"
          aria-label="Natural language command"
        />
        <button style={styles.button} type="submit" disabled={loading}>
          {loading ? "Parsing…" : "Send"}
        </button>
      </form>

      <div style={styles.examples}>
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            style={styles.exBtn}
            onClick={() => {
              setInput(ex);
              executeCommand(ex);
            }}
          >
            {ex}
          </button>
        ))}
      </div>

      {error && <p style={styles.error}>⚠ {error}</p>}

      {result && (
        <div style={styles.result}>
          <p style={styles.label}>
            {REGION_FLAG[result.query.region] ?? "🌏"} Parsed Query
          </p>
          <table style={styles.table}>
            <tbody>
              {Object.entries(result.query).map(([k, v]) => (
                <tr key={k}>
                  <td style={styles.tdKey}>{k}</td>
                  <td style={styles.tdVal}>
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <p style={styles.ts}>
            Parsed at {result.timestamp.toLocaleTimeString()}
          </p>
        </div>
      )}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { background: "#1e293b", borderRadius: 12, padding: 24, marginBottom: 24 },
  heading: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  sub: { color: "#94a3b8", marginBottom: 16, fontSize: 14 },
  form: { display: "flex", gap: 8, marginBottom: 12 },
  input: {
    flex: 1,
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #334155",
    background: "#0f172a",
    color: "#e2e8f0",
    fontSize: 14,
    outline: "none",
  },
  button: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    background: "#3b82f6",
    color: "#fff",
    fontWeight: 600,
    cursor: "pointer",
  },
  examples: { display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 16 },
  exBtn: {
    fontSize: 12,
    padding: "4px 10px",
    borderRadius: 20,
    border: "1px solid #334155",
    background: "transparent",
    color: "#94a3b8",
    cursor: "pointer",
  },
  error: { color: "#f87171", marginBottom: 12 },
  result: {
    background: "#0f172a",
    borderRadius: 8,
    padding: 16,
    border: "1px solid #334155",
  },
  label: { fontWeight: 600, marginBottom: 10, color: "#60a5fa" },
  table: { width: "100%", borderCollapse: "collapse" },
  tdKey: { padding: "4px 8px", color: "#94a3b8", fontFamily: "monospace", width: "40%" },
  tdVal: { padding: "4px 8px", fontFamily: "monospace" },
  ts: { marginTop: 10, fontSize: 12, color: "#475569" },
};
