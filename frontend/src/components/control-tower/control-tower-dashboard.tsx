"use client";

import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
} from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

interface OrchestrationResult {
  action_id?: string;
  parsed_command?: {
    query_type: string;
    region: string;
    metric: string;
  };
  analysis?: {
    summary: string;
    severity: string;
    confidence: number;
  };
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

interface MetricPayload {
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

function useNLOrchestration() {
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<OrchestrationResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function executeCommand(input: string) {
    setIsLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/agent/orchestrate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: input, user_id: `user_${Date.now()}` }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || "Orchestration failed");
      }

      const data = (await response.json()) as OrchestrationResult;
      setResult(data);

      await fetch("/api/audit/log", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          event_type: "nl_command_executed",
          user_input: input,
          execution_path: data.execution_path,
          timestamp: new Date().toISOString(),
        }),
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setIsLoading(false);
    }
  }

  return { executeCommand, result, isLoading, error };
}

function useRealTimeMetrics() {
  const [metrics, setMetrics] = useState<Record<string, MetricPayload>>({});
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    const eventSource = new EventSource("/api/sse/metrics");

    eventSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data) as MetricPayload;
        setMetrics((prev) => ({ ...prev, [data.region]: data }));
      } catch {
        /* ignore malformed chunks */
      }
    };

    eventSource.onerror = () => eventSource.close();
    eventSourceRef.current = eventSource;

    return () => {
      eventSourceRef.current?.close();
    };
  }, []);

  return metrics;
}

async function submitHitlDecision(
  decisionId: string,
  approvalChoice: "approve" | "reject",
) {
  await fetch("/api/agent/hitl/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision_id: decisionId,
      approval_choice: approvalChoice,
      user_id: "dashboard_user",
    }),
  });
}

export function NLCommandBar() {
  const [input, setInput] = useState("");
  const { executeCommand, result, isLoading, error } = useNLOrchestration();

  const suggestions = [
    "Show delivery bottlenecks in KL right now",
    "Forecast demand for next week by region",
    "Analyze cost trends across all routes",
    "Check for fraud patterns in recent transactions",
  ];

  function handleSubmit() {
    const trimmed = input.trim();
    if (!trimmed) return;
    executeCommand(trimmed);
    setInput("");
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-4 rounded-xl border border-blue-500/30 bg-gradient-to-r from-slate-900 to-slate-800 p-6"
    >
      <div className="flex flex-col gap-2 sm:flex-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleSubmit()}
          placeholder="Try: Show KL bottlenecks or Analyze fraud patterns"
          className="flex-1 rounded-lg border border-slate-600 bg-slate-950 px-4 py-3 text-slate-100 placeholder:text-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500"
          disabled={isLoading}
        />
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isLoading || !input.trim()}
          className="rounded-lg bg-blue-600 px-6 py-3 font-medium text-white transition hover:bg-blue-500 disabled:opacity-50"
        >
          {isLoading ? "Processing…" : "Execute"}
        </button>
      </div>

      {!result && (
        <div className="flex flex-wrap gap-2">
          {suggestions.map((cmd) => (
            <button
              key={cmd}
              type="button"
              onClick={() => executeCommand(cmd)}
              className="rounded-full border border-slate-600 bg-slate-900 px-3 py-1 text-xs text-slate-300 transition hover:border-blue-500"
            >
              {cmd}
            </button>
          ))}
        </div>
      )}

      <AnimatePresence>
        {result && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            className="space-y-3 rounded-lg border border-emerald-500/30 bg-slate-950/80 p-4"
          >
            <p className="text-xs text-slate-400">
              Path: {result.execution_path.join(" → ")} · mode: {result.llm_mode}
            </p>

            {result.parsed_command && (
              <p className="text-sm text-slate-300">
                {result.parsed_command.query_type} · {result.parsed_command.region} ·{" "}
                {result.parsed_command.metric}
              </p>
            )}

            {result.analysis && (
              <div className="space-y-1 text-sm">
                <p className="text-slate-200">{result.analysis.summary}</p>
                <span
                  className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
                    result.analysis.severity === "critical"
                      ? "bg-red-500/20 text-red-300"
                      : result.analysis.severity === "high"
                        ? "bg-orange-500/20 text-orange-300"
                        : "bg-yellow-500/20 text-yellow-300"
                  }`}
                >
                  {result.analysis.severity.toUpperCase()}
                </span>
              </div>
            )}

            {result.decision && (
              <DecisionDisplay
                decision={result.decision}
                slackMessageTs={result.slack_message_ts}
              />
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {error && (
        <div className="flex items-start gap-2 rounded-lg border border-red-500/40 bg-red-950/40 p-3 text-sm text-red-200">
          <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}
    </motion.div>
  );
}

function DecisionDisplay({
  decision,
  slackMessageTs,
}: {
  decision: NonNullable<OrchestrationResult["decision"]>;
  slackMessageTs?: string;
}) {
  const [status, setStatus] = useState<string | null>(null);

  async function handleChoice(choice: "approve" | "reject") {
    if (!slackMessageTs) return;
    await submitHitlDecision(slackMessageTs, choice);
    setStatus(choice === "approve" ? "Approved" : "Rejected");
  }

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.98 }}
      animate={{ opacity: 1, scale: 1 }}
      className="space-y-3 rounded-lg border border-slate-700 bg-slate-900/60 p-4"
    >
      <div className="flex items-center gap-2">
        {decision.requires_approval ? (
          <AlertTriangle className="h-5 w-5 text-orange-400" />
        ) : (
          <CheckCircle2 className="h-5 w-5 text-emerald-400" />
        )}
        <span className="font-semibold text-slate-200">
          {decision.requires_approval ? "AWAITING APPROVAL" : "AUTO-EXECUTED"}
        </span>
      </div>

      <p className="text-sm text-slate-400">{decision.reasoning}</p>
      <p className="text-sm text-slate-300">
        Action: <span className="font-mono">{decision.target_action}</span> · Impact: RM
        {decision.estimated_impact.toLocaleString()}
      </p>

      {decision.requires_approval && slackMessageTs && !status && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => handleChoice("approve")}
            className="flex-1 rounded bg-emerald-600/20 py-2 text-sm font-semibold text-emerald-300 hover:bg-emerald-600/30"
          >
            Approve
          </button>
          <button
            type="button"
            onClick={() => handleChoice("reject")}
            className="flex-1 rounded bg-red-600/20 py-2 text-sm font-semibold text-red-300 hover:bg-red-600/30"
          >
            Reject
          </button>
        </div>
      )}

      {status && <p className="text-sm font-medium text-emerald-300">{status}</p>}
    </motion.div>
  );
}

export function MetricsGrid() {
  const metrics = useRealTimeMetrics();
  const regions = ["MY", "SG", "HK", "TW"];

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.1 }}
      className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4"
    >
      {regions.map((region) => (
        <MetricCard key={region} region={region} data={metrics[region]} />
      ))}
    </motion.div>
  );
}

function MetricCard({ region, data }: { region: string; data?: MetricPayload }) {
  if (!data) {
    return (
      <div className="animate-pulse rounded-lg border border-slate-700 p-4">
        <div className="mb-3 h-4 w-1/2 rounded bg-slate-700" />
        <div className="h-3 rounded bg-slate-800" />
      </div>
    );
  }

  const statusColor =
    data.congestion < 60
      ? "border-emerald-500/30 bg-emerald-950/20"
      : data.congestion < 80
        ? "border-yellow-500/30 bg-yellow-950/20"
        : "border-red-500/30 bg-red-950/20";

  return (
    <motion.div layout className={`rounded-lg border p-4 ${statusColor}`}>
      <div className="mb-3 flex items-center justify-between">
        <h3 className="text-lg font-bold text-slate-100">{region}</h3>
        {data.congestion < 60 ? (
          <TrendingUp className="h-4 w-4 text-emerald-400" />
        ) : (
          <AlertTriangle className="h-4 w-4 text-yellow-400" />
        )}
      </div>
      <div className="mb-2 flex justify-between text-sm text-slate-300">
        <span>Congestion</span>
        <span className="font-mono font-semibold">{data.congestion}%</span>
      </div>
      <div className="mb-3 h-2 rounded-full bg-slate-800">
        <div
          className={`h-2 rounded-full transition-all ${
            data.congestion < 60
              ? "bg-emerald-500"
              : data.congestion < 80
                ? "bg-yellow-500"
                : "bg-red-500"
          }`}
          style={{ width: `${data.congestion}%` }}
        />
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs text-slate-400">
        <div>
          <p>Deliveries</p>
          <p className="font-semibold text-slate-200">{data.active_deliveries}</p>
        </div>
        <div>
          <p>Avg time</p>
          <p className="font-semibold text-slate-200">{data.avg_delivery_time}h</p>
        </div>
      </div>
    </motion.div>
  );
}

export function AgentActivityLog() {
  const [activities, setActivities] = useState<AgentLogEntry[]>([]);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    const stream = new EventSource("/api/sse/agent-log");
    stream.onmessage = (event) => {
      try {
        const log = JSON.parse(event.data) as AgentLogEntry;
        if (!log.node) return;
        setActivities((prev) => [log, ...prev].slice(0, 50));
      } catch {
        /* ignore */
      }
    };
    return () => stream.close();
  }, []);

  if (!isOpen) {
    return (
      <button
        type="button"
        onClick={() => setIsOpen(true)}
        className="fixed bottom-6 right-6 rounded-full bg-blue-600 px-4 py-2 text-sm font-medium text-white shadow-lg hover:bg-blue-500"
      >
        Agent log ({activities.length})
      </button>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, x: 400 }}
      animate={{ opacity: 1, x: 0 }}
      className="fixed bottom-6 right-6 flex max-h-96 w-96 flex-col overflow-hidden rounded-lg border border-slate-700 bg-slate-900 shadow-2xl"
    >
      <div className="flex items-center justify-between bg-blue-700 px-4 py-3">
        <h3 className="font-semibold text-white">Agent activity</h3>
        <button type="button" onClick={() => setIsOpen(false)} className="text-white">
          ✕
        </button>
      </div>
      <div className="max-h-80 space-y-2 overflow-y-auto p-3 font-mono text-xs">
        {activities.length === 0 ? (
          <p className="text-slate-500">Run a command to see agent hops…</p>
        ) : (
          activities.map((log, index) => (
            <motion.div
              key={`${log.timestamp}-${index}`}
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              className="rounded border border-slate-700 bg-slate-950 p-2 text-slate-300"
            >
              [{new Date(log.timestamp).toLocaleTimeString()}] {log.node} → {log.message}
            </motion.div>
          ))
        )}
      </div>
    </motion.div>
  );
}

export function ControlTowerDashboard() {
  return (
    <div className="mx-auto max-w-7xl space-y-6 p-6">
      <header className="space-y-1">
        <h1 className="text-3xl font-bold text-slate-50">NexusFlow Control Tower</h1>
        <p className="text-slate-400">
          LangGraph orchestration · SSE metrics · HITL · audit trail
        </p>
      </header>
      <NLCommandBar />
      <MetricsGrid />
      <AgentActivityLog />
    </div>
  );
}
