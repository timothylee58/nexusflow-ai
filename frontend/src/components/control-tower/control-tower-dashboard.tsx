"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertCircle,
  Building2,
  ChevronRight,
  Command,
  Download,
  Loader2,
  TrendingUp,
  AlertTriangle,
  Wifi,
  WifiOff,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { AlertList } from "@/components/nexusops/AlertList";
import { ActionDetails } from "@/components/nexusops/ActionDetails";
import { ConfirmationPanel } from "@/components/nexusops/ConfirmationPanel";
import { useSSE } from "@/hooks/useSSE";
import { apiFetch, getOrgId, setOrgId } from "@/lib/api";

/* ─── Types ─────────────────────────────────────────────────────────────── */

interface OrchestrationResult {
  action_id?: string;
  parsed_command?: { query_type: string; region: string; metric: string };
  analysis?: { summary: string; severity: string; confidence: number };
  decision?: {
    target_action: string;
    estimated_impact: number;
    requires_approval: boolean;
    reasoning: string;
  };
  execution_status: string;
  slack_message_ts?: string;
  execution_path: string[];
  llm_mode?: string;
  errors?: string[];
}

interface RegionMetrics {
  region: string;
  congestion: number;
  avg_delivery_time: number;
  active_deliveries: number;
  active_incidents: number;
}

interface AgentLogEntry {
  node: string;
  message: string;
  timestamp: string;
}

/* ─── NL Command Bar ─────────────────────────────────────────────────────── */

const SUGGESTIONS = [
  "Show delivery bottlenecks in KL right now",
  "Forecast demand for next week by region",
  "Analyze cost trends across all routes",
  "Check for fraud patterns in recent transactions",
];

function NLCommandBar({
  onResult,
}: {
  onResult: (r: OrchestrationResult | null, loading: boolean) => void;
}) {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function executeCommand(query: string) {
    const trimmed = query.trim();
    if (!trimmed) return;
    setIsLoading(true);
    setError(null);
    onResult(null, true);
    setInput("");

    try {
      const res = await apiFetch("/api/agent/orchestrate", {
        method: "POST",
        body: JSON.stringify({ query: trimmed, user_id: `user_${Date.now()}` }),
      });
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as OrchestrationResult;
      onResult(data, false);

      await apiFetch("/api/audit/log", {
        method: "POST",
        body: JSON.stringify({
          event_type: "nl_command_executed",
          user_input: trimmed,
          execution_path: data.execution_path,
          timestamp: new Date().toISOString(),
        }),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
      onResult(null, false);
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl border border-primary/20 bg-gradient-to-r from-slate-900 to-slate-800 p-5 space-y-3"
    >
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        <Command className="h-3.5 w-3.5" />
        <span>Natural Language Orchestration</span>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && executeCommand(input)}
          placeholder="Try: Show KL bottlenecks or Analyze fraud patterns…"
          className="flex-1 rounded-lg border border-border bg-background/80 px-4 py-2.5 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          disabled={isLoading}
        />
        <Button
          onClick={() => executeCommand(input)}
          disabled={isLoading || !input.trim()}
          className="gap-2"
        >
          {isLoading ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Processing…
            </>
          ) : (
            <>
              Execute
              <ChevronRight className="h-4 w-4" />
            </>
          )}
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {SUGGESTIONS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => executeCommand(s)}
            disabled={isLoading}
            className="rounded-full border border-border bg-secondary/40 px-2.5 py-1 text-xs text-muted-foreground transition hover:border-primary/40 hover:text-foreground disabled:opacity-40"
          >
            {s}
          </button>
        ))}
      </div>

      <AnimatePresence>
        {error && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-red-300"
          >
            <AlertCircle className="h-4 w-4 shrink-0" />
            {error}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

/* ─── Metrics Grid ───────────────────────────────────────────────────────── */

function MetricCard({ region, data }: { region: string; data?: RegionMetrics }) {
  if (!data) {
    return (
      <div className="animate-pulse rounded-xl border border-border p-4">
        <div className="mb-3 h-4 w-1/2 rounded bg-muted" />
        <div className="space-y-2">
          <div className="h-2 rounded bg-muted/60" />
          <div className="h-3 rounded bg-muted/40" />
        </div>
      </div>
    );
  }

  const { congestion, active_deliveries, avg_delivery_time, active_incidents } = data;
  const ringColor =
    congestion < 60
      ? "border-emerald-500/30"
      : congestion < 80
        ? "border-yellow-500/30"
        : "border-red-500/30";
  const barColor =
    congestion < 60 ? "bg-emerald-500" : congestion < 80 ? "bg-yellow-500" : "bg-red-500";

  return (
    <motion.div layout className={`rounded-xl border p-4 space-y-3 ${ringColor}`}>
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-bold">{region}</h3>
        <div className="flex items-center gap-1.5">
          {active_incidents > 0 && (
            <Badge variant="warning" className="text-[10px] px-1.5">
              {active_incidents}
            </Badge>
          )}
          {congestion < 60 ? (
            <TrendingUp className="h-4 w-4 text-emerald-400" />
          ) : (
            <AlertTriangle className="h-4 w-4 text-yellow-400" />
          )}
        </div>
      </div>

      <div>
        <div className="mb-1 flex justify-between text-xs text-muted-foreground">
          <span>Congestion</span>
          <span className="font-mono font-semibold text-foreground">{congestion}%</span>
        </div>
        <div className="h-1.5 overflow-hidden rounded-full bg-muted">
          <motion.div
            className={`h-full rounded-full ${barColor}`}
            animate={{ width: `${congestion}%` }}
            transition={{ duration: 0.4, ease: "easeOut" }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs text-muted-foreground">
        <div>
          <p>Deliveries</p>
          <p className="font-semibold text-foreground">{active_deliveries.toLocaleString()}</p>
        </div>
        <div>
          <p>Avg time</p>
          <p className="font-semibold text-foreground">{avg_delivery_time}h</p>
        </div>
      </div>
    </motion.div>
  );
}

function MetricsGrid() {
  const [metrics, setMetrics] = useState<Record<string, RegionMetrics>>({});
  const regions = ["MY", "SG", "HK", "TW"];

  const { connected } = useSSE<RegionMetrics>({
    url: "/api/sse/metrics",
    onMessage: (m) => setMetrics((prev) => ({ ...prev, [m.region]: m })),
  });

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wider">
          Regional Operations
        </h2>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
          {connected ? (
            <Wifi className="h-3 w-3 text-emerald-400" />
          ) : (
            <WifiOff className="h-3 w-3" />
          )}
          {connected ? "Live" : "Connecting…"}
        </div>
      </div>
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="grid grid-cols-2 gap-3 lg:grid-cols-4"
      >
        {regions.map((r) => (
          <MetricCard key={r} region={r} data={metrics[r]} />
        ))}
      </motion.div>
    </div>
  );
}

/* ─── Agent Activity Log ─────────────────────────────────────────────────── */

function AgentActivityLog() {
  const [entries, setEntries] = useState<AgentLogEntry[]>([]);
  const [open, setOpen] = useState(false);

  useSSE<AgentLogEntry>({
    url: "/api/sse/agent-log",
    onMessage: (log) => {
      if (!log.node) return;
      setEntries((prev) => [log, ...prev].slice(0, 50));
    },
  });

  const count = entries.length;

  return (
    <>
      <motion.button
        type="button"
        onClick={() => setOpen((v) => !v)}
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
        className="fixed bottom-6 right-6 flex items-center gap-2 rounded-full bg-primary px-4 py-2 text-sm font-medium text-primary-foreground shadow-lg"
      >
        <Activity className="h-4 w-4" />
        Agent log
        {count > 0 && (
          <span className="rounded-full bg-white/20 px-1.5 py-0.5 text-xs leading-none">
            {count}
          </span>
        )}
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, x: 320, scale: 0.95 }}
            animate={{ opacity: 1, x: 0, scale: 1 }}
            exit={{ opacity: 0, x: 320, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 300, damping: 30 }}
            className="fixed bottom-16 right-6 flex max-h-[420px] w-96 flex-col overflow-hidden rounded-xl border border-border bg-card shadow-2xl"
          >
            <div className="flex items-center justify-between bg-primary/10 px-4 py-3">
              <div className="flex items-center gap-2">
                <Activity className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Agent Activity</h3>
              </div>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded p-1 text-muted-foreground hover:text-foreground"
              >
                ✕
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-3 space-y-1.5 font-mono text-xs">
              {entries.length === 0 ? (
                <p className="py-4 text-center text-muted-foreground">
                  Run a command to see agent hops…
                </p>
              ) : (
                <AnimatePresence initial={false}>
                  {entries.map((log, i) => (
                    <motion.div
                      key={`${log.timestamp}-${i}`}
                      initial={{ opacity: 0, y: -6 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="rounded border border-border bg-background p-2 text-foreground/80"
                    >
                      <span className="text-muted-foreground">
                        [{new Date(log.timestamp).toLocaleTimeString()}]
                      </span>{" "}
                      <span className="text-primary">{log.node}</span>
                      <ChevronRight className="inline h-3 w-3 text-muted-foreground" />
                      {log.message}
                    </motion.div>
                  ))}
                </AnimatePresence>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}

/* ─── Org-ID Switcher ────────────────────────────────────────────────────── */

function OrgSwitcher() {
  const [orgId, setOrgIdState] = useState(() => getOrgId());
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(orgId);

  function save() {
    const trimmed = draft.trim() || "default";
    setOrgId(trimmed);
    setOrgIdState(trimmed);
    setEditing(false);
  }

  return (
    <div className="flex items-center gap-2 text-xs text-muted-foreground">
      <Building2 className="h-3.5 w-3.5" />
      {editing ? (
        <>
          <input
            autoFocus
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
            className="w-28 rounded border border-border bg-background px-1.5 py-0.5 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring"
          />
          <button type="button" onClick={save} className="text-primary hover:underline">Save</button>
        </>
      ) : (
        <>
          <span className="font-mono">{orgId}</span>
          <button type="button" onClick={() => { setDraft(orgId); setEditing(true); }} className="hover:text-foreground">
            edit
          </button>
        </>
      )}
    </div>
  );
}

/* ─── Audit Export Button ────────────────────────────────────────────────── */

function AuditExportButton() {
  const [busy, setBusy] = useState(false);

  async function downloadCsv() {
    setBusy(true);
    try {
      const res = await apiFetch("/api/audit/export?format=csv");
      if (!res.ok) throw new Error(`Export failed: ${res.status}`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `audit_${getOrgId()}_${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Audit export error", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={downloadCsv} disabled={busy} className="gap-1.5 text-xs">
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
      Export audit CSV
    </Button>
  );
}

/* ─── Main Dashboard ─────────────────────────────────────────────────────── */

export function ControlTowerDashboard() {
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [loading, setLoading] = useState(false);

  function handleResult(r: OrchestrationResult | null, isLoading: boolean) {
    setResult(r);
    setLoading(isLoading);
  }

  const showAction = loading || result !== null;
  const showHitl =
    result?.decision?.requires_approval && result?.slack_message_ts && !loading;

  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <motion.header
        initial={{ opacity: 0, y: -12 }}
        animate={{ opacity: 1, y: 0 }}
        className="flex items-start justify-between gap-4"
      >
        <div className="space-y-1">
          <h1 className="text-3xl font-bold tracking-tight">NexusOps Control Tower</h1>
          <p className="text-muted-foreground">
            LangGraph orchestration · SSE real-time metrics · HITL approval · audit trail
          </p>
        </div>
        <div className="flex flex-col items-end gap-2 pt-1">
          <OrgSwitcher />
          <AuditExportButton />
        </div>
      </motion.header>

      <NLCommandBar onResult={handleResult} />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left column: metrics + alerts */}
        <div className="space-y-6 lg:col-span-2">
          <MetricsGrid />
          <AlertList />
        </div>

        {/* Right column: action details + HITL */}
        <div className="space-y-4">
          <AnimatePresence>
            {showAction && (
              <motion.div
                key="action"
                initial={{ opacity: 0, x: 16 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 16 }}
              >
                <ActionDetails result={result!} isLoading={loading} />
              </motion.div>
            )}
          </AnimatePresence>

          <AnimatePresence>
            {showHitl && result!.decision && (
              <motion.div
                key="hitl"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ delay: 0.15 }}
              >
                <ConfirmationPanel
                  decisionId={result!.slack_message_ts!}
                  action={result!.decision!.target_action}
                  reasoning={result!.decision!.reasoning}
                  estimatedImpact={result!.decision!.estimated_impact}
                  requiresApproval={result!.decision!.requires_approval}
                  onResolved={(choice) => {
                    setResult((prev) =>
                      prev
                        ? {
                            ...prev,
                            execution_status: choice === "approve" ? "completed" : "rejected",
                          }
                        : prev,
                    );
                  }}
                />
              </motion.div>
            )}
          </AnimatePresence>

          {!showAction && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
            >
              <Card>
                <CardContent className="flex h-48 flex-col items-center justify-center gap-3 text-center">
                  <Command className="h-8 w-8 text-muted-foreground/40" />
                  <div>
                    <p className="text-sm font-medium text-muted-foreground">
                      No active action
                    </p>
                    <p className="text-xs text-muted-foreground/60">
                      Run a command to see details here
                    </p>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          )}
        </div>
      </div>

      <AgentActivityLog />
    </div>
  );
}
