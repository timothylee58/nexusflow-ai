/**
 * OddleDispatcher – Weeks 3-4 Human-in-the-Loop Dispatch Panel
 */
import React, { useState } from "react";
import { useDispatch } from "../hooks/useDispatch";

const SAMPLE_INCIDENTS = [
  {
    incident_id: "INC-001",
    location: "Federal Highway, KL",
    region: "MY",
    description: "Major jam – estimated 40-minute delay",
  },
  {
    incident_id: "INC-002",
    location: "PIE, Singapore",
    region: "SG",
    description: "Accident blocking 2 lanes, 25-minute delay",
  },
];

export default function OddleDispatcher() {
  const { analyseIncident, result, loading, error } = useDispatch();
  const [approved, setApproved] = useState<string | null>(null);

  return (
    <section style={styles.section}>
      <h2 style={styles.heading}>🚚 Oddle Autonomous Dispatcher</h2>
      <p style={styles.sub}>
        AI detects incidents, calculates impact, proposes reroutes. Managers
        approve or reject.
      </p>

      <div style={styles.incidentGrid}>
        {SAMPLE_INCIDENTS.map((inc) => (
          <button
            key={inc.incident_id}
            style={styles.incBtn}
            onClick={() => analyseIncident(inc)}
            disabled={loading}
          >
            <span style={styles.incId}>{inc.incident_id}</span>
            <span style={styles.incLoc}>{inc.location}</span>
            <span style={styles.incDesc}>{inc.description}</span>
          </button>
        ))}
      </div>

      {loading && <p style={styles.loading}>🤖 Analysing incident…</p>}
      {error && <p style={styles.error}>⚠ {error}</p>}

      {result && !loading && (
        <div style={styles.result}>
          <div style={styles.decisionBanner}>
            <span style={actionStyle(String(result.decision["action"]))}>
              {String(result.decision["action"])}
            </span>
            <span style={styles.saving}>
              Est. saving: ${Number(result.decision["net_saving_usd"] ?? 0).toFixed(2)}
            </span>
          </div>

          <p style={styles.reasoning}>
            💬 {String(result.decision["reasoning"] ?? "")}
          </p>

          <div style={styles.impactRow}>
            <Stat
              label="Affected Deliveries"
              value={String(result.impact["affected_deliveries"] ?? "—")}
            />
            <Stat
              label="Delay Cost"
              value={`$${Number(result.impact["estimated_delay_cost_usd"] ?? 0).toFixed(2)}`}
            />
            <Stat
              label="Severity"
              value={String(result.severity["severity"] ?? "—").toUpperCase()}
            />
          </div>

          {approved === result.incident_id ? (
            <p style={styles.approved}>
              ✅ Approved – SMS dispatched to drivers
            </p>
          ) : (
            <div style={styles.actions}>
              <button
                style={styles.approveBtn}
                onClick={() => setApproved(result.incident_id)}
              >
                ✅ APPROVE
              </button>
              <button style={styles.rejectBtn} onClick={() => setApproved(null)}>
                ❌ REJECT
              </button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ textAlign: "center" }}>
      <div style={{ fontSize: 22, fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: 12, color: "#94a3b8" }}>{label}</div>
    </div>
  );
}

function actionStyle(action: string): React.CSSProperties {
  const colours: Record<string, string> = {
    REROUTE: "#22c55e",
    MONITOR: "#f59e0b",
    ESCALATE: "#ef4444",
  };
  return {
    fontWeight: 700,
    fontSize: 18,
    color: colours[action] ?? "#e2e8f0",
  };
}

const styles: Record<string, React.CSSProperties> = {
  section: { background: "#1e293b", borderRadius: 12, padding: 24, marginBottom: 24 },
  heading: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  sub: { color: "#94a3b8", marginBottom: 16, fontSize: 14 },
  incidentGrid: { display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 16 },
  incBtn: {
    flex: "1 1 220px",
    padding: 14,
    borderRadius: 8,
    border: "1px solid #334155",
    background: "#0f172a",
    color: "#e2e8f0",
    cursor: "pointer",
    textAlign: "left",
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  incId: { fontSize: 11, color: "#60a5fa", fontFamily: "monospace" },
  incLoc: { fontWeight: 600, fontSize: 14 },
  incDesc: { fontSize: 12, color: "#94a3b8" },
  loading: { color: "#60a5fa", marginBottom: 12 },
  error: { color: "#f87171", marginBottom: 12 },
  result: {
    background: "#0f172a",
    borderRadius: 8,
    padding: 16,
    border: "1px solid #334155",
  },
  decisionBanner: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 10,
  },
  saving: { color: "#22c55e", fontWeight: 600 },
  reasoning: { color: "#94a3b8", fontSize: 14, marginBottom: 14 },
  impactRow: {
    display: "flex",
    justifyContent: "space-around",
    marginBottom: 16,
  },
  actions: { display: "flex", gap: 12 },
  approveBtn: {
    flex: 1,
    padding: "10px 0",
    borderRadius: 8,
    border: "none",
    background: "#16a34a",
    color: "#fff",
    fontWeight: 700,
    cursor: "pointer",
  },
  rejectBtn: {
    flex: 1,
    padding: "10px 0",
    borderRadius: 8,
    border: "none",
    background: "#dc2626",
    color: "#fff",
    fontWeight: 700,
    cursor: "pointer",
  },
  approved: { color: "#22c55e", fontWeight: 600 },
};
