/**
 * ModelRouter – Weeks 7-8 cost-optimisation dashboard
 */
import React, { useState } from "react";
import { useModelRouter } from "../hooks/useModelRouter";

const SAMPLE_QUERIES = [
  { label: "Simple status", query: "What is order #12345 status?" },
  { label: "Route optimise", query: "Optimise delivery routes for 50 KL drops tomorrow" },
  { label: "Fraud flag", query: "Transaction TXN-9999 looks suspicious – $75,000 refund" },
];

export default function ModelRouter() {
  const { routeQuery, routeResult, stats, loading, error } = useModelRouter();
  const [input, setInput] = useState("");

  const MODEL_COLOUR: Record<string, string> = {
    haiku: "#22c55e",
    sonnet: "#f59e0b",
    opus: "#ef4444",
  };

  const modelColor = (model: string) => {
    const key = Object.keys(MODEL_COLOUR).find((k) => model.includes(k));
    return MODEL_COLOUR[key ?? ""] ?? "#94a3b8";
  };

  return (
    <section style={styles.section}>
      <h2 style={styles.heading}>⚡ Intelligent Model Router</h2>
      <p style={styles.sub}>
        Routes each query to the cheapest model able to handle it, saving up to
        92.6% vs using the premium model for everything.
      </p>

      {/* Stats bar */}
      {stats && (
        <div style={styles.statsBar}>
          <StatCard label="Total Queries" value={String(stats.total_queries)} />
          <StatCard
            label="Haiku (cheap)"
            value={String(stats.breakdown.haiku)}
            color="#22c55e"
          />
          <StatCard
            label="Sonnet"
            value={String(stats.breakdown.sonnet)}
            color="#f59e0b"
          />
          <StatCard
            label="Opus (premium)"
            value={String(stats.breakdown.opus)}
            color="#ef4444"
          />
          <StatCard
            label="Total Cost"
            value={`$${stats.total_cost_usd.toFixed(4)}`}
          />
          <StatCard
            label="Savings"
            value={`${stats.savings_pct.toFixed(1)}%`}
            color="#22c55e"
          />
        </div>
      )}

      {/* Quick samples */}
      <div style={styles.samples}>
        {SAMPLE_QUERIES.map(({ label, query }) => (
          <button
            key={label}
            style={styles.sampleBtn}
            onClick={() => routeQuery(query)}
            disabled={loading}
          >
            {label}
          </button>
        ))}
      </div>

      {/* Custom query */}
      <div style={styles.inputRow}>
        <input
          style={styles.input}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your own query…"
          onKeyDown={(e) => e.key === "Enter" && input.trim() && routeQuery(input.trim())}
        />
        <button
          style={styles.btn}
          onClick={() => input.trim() && routeQuery(input.trim())}
          disabled={loading}
        >
          {loading ? "Routing…" : "Route"}
        </button>
      </div>

      {error && <p style={styles.error}>⚠ {error}</p>}

      {routeResult && !loading && (
        <div style={styles.result}>
          <div style={styles.metaRow}>
            <span
              style={{
                fontWeight: 700,
                color: modelColor(routeResult.model_used),
              }}
            >
              {routeResult.model_used}
            </span>
            <span style={styles.complexity}>{routeResult.complexity}</span>
            <span style={styles.cost}>${routeResult.cost_usd.toFixed(6)}</span>
            <span style={styles.tokens}>{routeResult.tokens_used} tokens</span>
          </div>
          <p style={styles.responseText}>{routeResult.response}</p>
        </div>
      )}
    </section>
  );
}

function StatCard({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div style={{ textAlign: "center", minWidth: 90 }}>
      <div style={{ fontSize: 20, fontWeight: 700, color: color ?? "#e2e8f0" }}>
        {value}
      </div>
      <div style={{ fontSize: 11, color: "#64748b" }}>{label}</div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { background: "#1e293b", borderRadius: 12, padding: 24, marginBottom: 24 },
  heading: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  sub: { color: "#94a3b8", marginBottom: 16, fontSize: 14 },
  statsBar: {
    display: "flex",
    gap: 16,
    flexWrap: "wrap",
    background: "#0f172a",
    borderRadius: 8,
    padding: 16,
    marginBottom: 16,
    border: "1px solid #334155",
  },
  samples: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 },
  sampleBtn: {
    padding: "6px 14px",
    borderRadius: 20,
    border: "1px solid #334155",
    background: "transparent",
    color: "#94a3b8",
    cursor: "pointer",
    fontSize: 13,
  },
  inputRow: { display: "flex", gap: 8, marginBottom: 12 },
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
  btn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    background: "#3b82f6",
    color: "#fff",
    fontWeight: 600,
    cursor: "pointer",
  },
  error: { color: "#f87171" },
  result: {
    background: "#0f172a",
    borderRadius: 8,
    padding: 16,
    border: "1px solid #334155",
  },
  metaRow: {
    display: "flex",
    gap: 16,
    alignItems: "center",
    marginBottom: 10,
    flexWrap: "wrap",
  },
  complexity: { fontSize: 12, color: "#64748b", textTransform: "uppercase" },
  cost: { fontSize: 12, color: "#22c55e" },
  tokens: { fontSize: 12, color: "#64748b" },
  responseText: { fontSize: 14, color: "#cbd5e1", lineHeight: 1.6 },
};
