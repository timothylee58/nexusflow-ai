"use client";

import { useEffect, useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  Bell,
  CheckCircle2,
  Clock,
  ExternalLink,
  Hash,
  Loader2,
  Settings,
  Shield,
  Slack,
  XCircle,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

interface SystemStatus {
  slack_configured: boolean;
  hitl_timeout_minutes: number;
  llm_provider: string;
  llm_configured: boolean;
  environment: string;
}

interface AuditEntry {
  id: string;
  event_type: string;
  user_id: string | null;
  user_input: string | null;
  approval_choice: string | null;
  created_at: string;
}

const EVENT_LABELS: Record<string, string> = {
  hitl_approve: "Approved via Slack",
  hitl_reject: "Rejected via Slack",
  hitl_timeout: "Timed out (auto-reject)",
  orchestration_executed: "Command executed",
  nl_command_executed: "NL command",
};

const EVENT_BADGE: Record<string, "success" | "destructive" | "warning" | "secondary"> = {
  hitl_approve: "success",
  hitl_reject: "destructive",
  hitl_timeout: "warning",
  orchestration_executed: "secondary",
  nl_command_executed: "secondary",
};

function ConnectionStatus({ configured }: { configured: boolean }) {
  return (
    <div
      className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${
        configured
          ? "border-emerald-500/30 bg-emerald-950/20 text-emerald-300"
          : "border-border bg-muted/20 text-muted-foreground"
      }`}
    >
      {configured ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-400" />
      ) : (
        <AlertCircle className="h-4 w-4 shrink-0" />
      )}
      {configured ? "Slack connected — HITL bot active" : "Slack not configured"}
    </div>
  );
}

function HITLDecisionRow({ entry }: { entry: AuditEntry }) {
  const isHitl = entry.event_type.startsWith("hitl_");
  const label = EVENT_LABELS[entry.event_type] ?? entry.event_type;
  const badgeVariant = EVENT_BADGE[entry.event_type] ?? "secondary";
  const ts = new Date(entry.created_at).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-start gap-3 py-3"
    >
      <div className="mt-0.5">
        {entry.event_type === "hitl_approve" && (
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        )}
        {entry.event_type === "hitl_reject" && (
          <XCircle className="h-4 w-4 text-red-400" />
        )}
        {entry.event_type === "hitl_timeout" && (
          <Clock className="h-4 w-4 text-yellow-400" />
        )}
        {!isHitl && <Bell className="h-4 w-4 text-muted-foreground" />}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <Badge variant={badgeVariant} className="text-[10px]">
            {label}
          </Badge>
          {entry.user_id && (
            <span className="text-xs text-muted-foreground">by {entry.user_id}</span>
          )}
        </div>
        {entry.user_input && (
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {entry.user_input}
          </p>
        )}
      </div>
      <span className="shrink-0 text-xs text-muted-foreground">{ts}</span>
    </motion.div>
  );
}

export function SlackSettings() {
  const [status, setStatus] = useState<SystemStatus | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  async function fetchData(isRefresh = false) {
    if (isRefresh) setRefreshing(true);
    try {
      const [statusRes, auditRes] = await Promise.all([
        fetch("/api/status").catch(() => null),
        fetch("/api/audit/recent?limit=30"),
      ]);

      if (statusRes?.ok) {
        setStatus(await statusRes.json());
      }

      if (auditRes.ok) {
        const data = await auditRes.json();
        setAuditLogs(data.items ?? []);
      }

      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 15_000);
    return () => clearInterval(interval);
  }, []);

  const hitlLogs = auditLogs.filter((l) => l.event_type.startsWith("hitl_"));
  const pendingCount = 0; // resolved via real-time SSE; shown for context

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="flex items-center gap-2 text-xl font-bold">
            <Slack className="h-5 w-5 text-[#4A154B]" />
            Slack Integration & HITL
          </h2>
          <p className="text-sm text-muted-foreground">
            Configure the Slack bot and review human-in-the-loop decisions
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => fetchData(true)}
          disabled={refreshing}
          className="gap-1.5"
        >
          {refreshing ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Settings className="h-3.5 w-3.5" />
          )}
          Refresh
        </Button>
      </div>

      {/* Connection status */}
      <AnimatePresence>
        {!loading && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="space-y-4"
          >
            <ConnectionStatus configured={status?.slack_configured ?? false} />

            <div className="grid gap-4 sm:grid-cols-2">
              {/* Config reference card */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Shield className="h-4 w-4 text-primary" />
                    Bot Configuration
                  </CardTitle>
                  <CardDescription>
                    Set these environment variables to activate Slack
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  {[
                    { key: "SLACK_BOT_TOKEN", desc: "xoxb-… (Bot User OAuth Token)" },
                    { key: "SLACK_SIGNING_SECRET", desc: "From Slack App Basic Info" },
                    { key: "SLACK_CHANNEL_ID", desc: "Channel to post HITL alerts" },
                    {
                      key: "HITL_TIMEOUT_MINUTES",
                      desc: `Auto-reject after (default: ${status?.hitl_timeout_minutes ?? 30} min)`,
                    },
                  ].map(({ key, desc }) => (
                    <div key={key}>
                      <code className="text-xs font-mono text-primary">{key}</code>
                      <p className="text-xs text-muted-foreground">{desc}</p>
                    </div>
                  ))}

                  <Separator />

                  <div className="space-y-1.5">
                    <p className="text-xs font-medium text-muted-foreground">
                      Slack Interactions URL
                    </p>
                    <code className="block rounded border border-border bg-muted/30 px-2 py-1 text-xs text-foreground">
                      https://&lt;your-domain&gt;/slack/interactions
                    </code>
                    <p className="text-xs text-muted-foreground">
                      Set this in Slack App → Interactivity & Shortcuts
                    </p>
                  </div>

                  <div className="pt-1">
                    <a
                      href="https://api.slack.com/apps"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                    >
                      Open Slack App Console
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  </div>
                </CardContent>
              </Card>

              {/* HITL flow card */}
              <Card>
                <CardHeader className="pb-3">
                  <CardTitle className="flex items-center gap-2 text-sm">
                    <Hash className="h-4 w-4 text-primary" />
                    HITL Confirmation Flow
                  </CardTitle>
                  <CardDescription>
                    How Slack and the Control Tower interact
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-3 text-xs text-muted-foreground">
                  {[
                    {
                      step: "1",
                      text: "Agent detects critical/high severity event and flags for approval",
                    },
                    {
                      step: "2",
                      text: "Block Kit message with Approve/Reject buttons posted to Slack channel",
                    },
                    {
                      step: "3",
                      text: `Button click → /slack/interactions → DB update + audit log`,
                    },
                    {
                      step: "4",
                      text: "Dashboard updates live via SSE; Slack message replaced with result",
                    },
                    {
                      step: "5",
                      text: `No response after ${status?.hitl_timeout_minutes ?? 30} min → auto-reject + thread notice`,
                    },
                  ].map(({ step, text }) => (
                    <div key={step} className="flex items-start gap-2">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/20 text-[10px] font-bold text-primary">
                        {step}
                      </span>
                      <p>{text}</p>
                    </div>
                  ))}
                </CardContent>
              </Card>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* HITL audit log */}
      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm">HITL Decision History</CardTitle>
            <Badge variant="outline" className="text-xs">
              {hitlLogs.length} decisions
            </Badge>
          </div>
          <CardDescription>
            All human approval events (Slack + Dashboard) from the audit trail
          </CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          {loading ? (
            <div className="flex h-24 items-center justify-center gap-2 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" />
              Loading…
            </div>
          ) : error ? (
            <div className="flex h-24 items-center justify-center gap-2 text-sm text-red-400">
              <AlertCircle className="h-4 w-4" />
              {error}
            </div>
          ) : auditLogs.length === 0 ? (
            <div className="flex h-24 items-center justify-center text-sm text-muted-foreground">
              No decisions recorded yet
            </div>
          ) : (
            <ul className="divide-y divide-border px-4">
              {auditLogs.map((entry) => (
                <li key={entry.id}>
                  <HITLDecisionRow entry={entry} />
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
