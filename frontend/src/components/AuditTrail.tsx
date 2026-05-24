/**
 * AuditTrail – Weeks 5-6 VidStega tamper-proof record viewer
 */
import React, { useState } from "react";

interface AuditResult {
  valid: boolean;
  audit_data?: Record<string, unknown>;
  error?: string;
  image_b64?: string;
  signature?: string;
}

export default function AuditTrail() {
  const [loading, setLoading] = useState(false);
  const [auditResult, setAuditResult] = useState<AuditResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const createAudit = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch("/api/audit/create", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          decision_id: `DEC-${Date.now()}`,
          ai_reasoning: {
            rule: "amount > $10K triggered enhanced review",
            confidence: 0.97,
            model: "claude-3-5-sonnet",
          },
          user_approval: "manager@nexusflow.ai",
          amount: 12500.0,
        }),
      });
      if (!response.ok) throw new Error(`API error ${response.status}`);
      const data = await response.json();
      setAuditResult({ valid: true, ...data });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const verifyAudit = async () => {
    if (!auditResult?.image_b64 || !auditResult?.signature) return;
    setLoading(true);
    try {
      const response = await fetch("/api/audit/verify", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          image_b64: auditResult.image_b64,
          signature: auditResult.signature,
        }),
      });
      if (!response.ok) throw new Error(`API error ${response.status}`);
      const data = await response.json();
      setAuditResult((prev) => ({ ...prev, ...data }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  return (
    <section style={styles.section}>
      <h2 style={styles.heading}>🔐 VidStega Audit Trail</h2>
      <p style={styles.sub}>
        AI reasoning is encrypted and hidden inside receipt images using LSB
        steganography. Regulators can verify decisions are untampered.
      </p>

      <div style={styles.actions}>
        <button style={styles.btn} onClick={createAudit} disabled={loading}>
          {loading ? "Working…" : "Create Audit Record"}
        </button>
        {auditResult?.image_b64 && (
          <button style={styles.btn2} onClick={verifyAudit} disabled={loading}>
            Verify Record
          </button>
        )}
      </div>

      {error && <p style={styles.error}>⚠ {error}</p>}

      {auditResult && (
        <div style={styles.result}>
          {auditResult.image_b64 && (
            <div style={styles.imageWrap}>
              <img
                src={`data:image/png;base64,${auditResult.image_b64}`}
                alt="Receipt with embedded audit data"
                style={styles.image}
              />
              <p style={styles.imageLabel}>
                Receipt (audit data hidden in LSB pixels)
              </p>
            </div>
          )}

          {auditResult.signature && (
            <div style={styles.sigBox}>
              <span style={styles.sigLabel}>HMAC-SHA256 Signature</span>
              <code style={styles.sig}>{auditResult.signature}</code>
            </div>
          )}

          {auditResult.audit_data && (
            <div style={styles.dataBox}>
              <p style={styles.valid}>
                {auditResult.valid ? "✅ Signature Valid" : "❌ Invalid / Tampered"}
              </p>
              <pre style={styles.pre}>
                {JSON.stringify(auditResult.audit_data, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </section>
  );
}

const styles: Record<string, React.CSSProperties> = {
  section: { background: "#1e293b", borderRadius: 12, padding: 24, marginBottom: 24 },
  heading: { fontSize: 20, fontWeight: 700, marginBottom: 8 },
  sub: { color: "#94a3b8", marginBottom: 16, fontSize: 14 },
  actions: { display: "flex", gap: 12, marginBottom: 16 },
  btn: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "none",
    background: "#7c3aed",
    color: "#fff",
    fontWeight: 600,
    cursor: "pointer",
  },
  btn2: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid #334155",
    background: "transparent",
    color: "#e2e8f0",
    fontWeight: 600,
    cursor: "pointer",
  },
  error: { color: "#f87171", marginBottom: 12 },
  result: {
    background: "#0f172a",
    borderRadius: 8,
    padding: 16,
    border: "1px solid #334155",
  },
  imageWrap: { marginBottom: 16, textAlign: "center" },
  image: { borderRadius: 8, border: "1px solid #334155", maxWidth: 200 },
  imageLabel: { fontSize: 12, color: "#64748b", marginTop: 6 },
  sigBox: { marginBottom: 12 },
  sigLabel: { fontSize: 12, color: "#94a3b8", display: "block", marginBottom: 4 },
  sig: {
    fontFamily: "monospace",
    fontSize: 11,
    color: "#a78bfa",
    wordBreak: "break-all",
    display: "block",
  },
  dataBox: { marginTop: 12 },
  valid: { fontWeight: 600, marginBottom: 8 },
  pre: {
    fontFamily: "monospace",
    fontSize: 12,
    color: "#a3e635",
    overflowX: "auto",
    whiteSpace: "pre-wrap",
  },
};
