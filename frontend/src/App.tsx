import React, { useState } from "react";
import ControlTower from "./components/ControlTower";
import OddleDispatcher from "./components/OddleDispatcher";
import AuditTrail from "./components/AuditTrail";
import ModelRouter from "./components/ModelRouter";

type Tab = "control-tower" | "dispatcher" | "audit" | "model-router";

const TABS: { id: Tab; label: string }[] = [
  { id: "control-tower", label: "🗼 Control Tower" },
  { id: "dispatcher", label: "🚚 Dispatcher" },
  { id: "audit", label: "🔐 Audit Trail" },
  { id: "model-router", label: "⚡ Model Router" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("control-tower");

  return (
    <div style={styles.app}>
      <header style={styles.header}>
        <div style={styles.logo}>
          <span style={styles.logoIcon}>🌐</span>
          <span style={styles.logoText}>NexusFlow AI</span>
        </div>
        <p style={styles.tagline}>
          Multi-Agent Autonomous Operations Platform · MY / SG / HK / TW
        </p>
      </header>

      <nav style={styles.nav}>
        {TABS.map((tab) => (
          <button
            key={tab.id}
            style={{
              ...styles.tabBtn,
              ...(activeTab === tab.id ? styles.tabBtnActive : {}),
            }}
            onClick={() => setActiveTab(tab.id)}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <main style={styles.main}>
        {activeTab === "control-tower" && <ControlTower />}
        {activeTab === "dispatcher" && <OddleDispatcher />}
        {activeTab === "audit" && <AuditTrail />}
        {activeTab === "model-router" && <ModelRouter />}
      </main>

      <footer style={styles.footer}>
        NexusFlow AI v1.0 · Powered by Anthropic Claude ·{" "}
        <span style={{ color: "#475569" }}>© 2026</span>
      </footer>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  app: {
    minHeight: "100vh",
    display: "flex",
    flexDirection: "column",
  },
  header: {
    padding: "24px 32px 16px",
    borderBottom: "1px solid #1e293b",
  },
  logo: { display: "flex", alignItems: "center", gap: 10, marginBottom: 4 },
  logoIcon: { fontSize: 28 },
  logoText: { fontSize: 24, fontWeight: 800, letterSpacing: "-0.5px" },
  tagline: { color: "#64748b", fontSize: 13 },
  nav: {
    display: "flex",
    gap: 4,
    padding: "12px 32px",
    borderBottom: "1px solid #1e293b",
    flexWrap: "wrap",
  },
  tabBtn: {
    padding: "8px 18px",
    borderRadius: 8,
    border: "none",
    background: "transparent",
    color: "#94a3b8",
    cursor: "pointer",
    fontWeight: 500,
    fontSize: 14,
    transition: "background 0.15s",
  },
  tabBtnActive: {
    background: "#1e293b",
    color: "#e2e8f0",
  },
  main: {
    flex: 1,
    padding: "24px 32px",
    maxWidth: 900,
    width: "100%",
    margin: "0 auto",
  },
  footer: {
    padding: "16px 32px",
    borderTop: "1px solid #1e293b",
    fontSize: 12,
    color: "#64748b",
    textAlign: "center",
  },
};
