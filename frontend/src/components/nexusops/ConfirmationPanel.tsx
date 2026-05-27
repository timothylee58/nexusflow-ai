"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertTriangle, CheckCircle2, Loader2, ShieldAlert, XCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";

interface ConfirmationPanelProps {
  decisionId: string;
  action: string;
  reasoning: string;
  estimatedImpact: number;
  requiresApproval: boolean;
  onResolved?: (choice: "approve" | "reject") => void;
}

type PanelState = "idle" | "pending" | "approved" | "rejected" | "error";

async function submitApproval(decisionId: string, choice: "approve" | "reject") {
  const res = await fetch("/api/agent/hitl/approve", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      decision_id: decisionId,
      approval_choice: choice,
      user_id: "dashboard_user",
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export function ConfirmationPanel({
  decisionId,
  action,
  reasoning,
  estimatedImpact,
  requiresApproval,
  onResolved,
}: ConfirmationPanelProps) {
  const [state, setState] = useState<PanelState>(requiresApproval ? "idle" : "approved");
  const [errorMsg, setErrorMsg] = useState("");

  async function handleChoice(choice: "approve" | "reject") {
    setState("pending");
    setErrorMsg("");
    try {
      await submitApproval(decisionId, choice);
      setState(choice === "approve" ? "approved" : "rejected");
      onResolved?.(choice);
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Request failed");
      setState("error");
    }
  }

  return (
    <Card
      className={`border-2 transition-colors duration-500 ${
        state === "approved"
          ? "border-emerald-500/40"
          : state === "rejected"
            ? "border-red-500/40"
            : state === "error"
              ? "border-destructive/40"
              : "border-orange-500/30"
      }`}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <ShieldAlert
            className={`h-5 w-5 ${
              state === "approved"
                ? "text-emerald-400"
                : state === "rejected"
                  ? "text-red-400"
                  : "text-orange-400"
            }`}
          />
          <CardTitle className="text-base">
            {state === "approved"
              ? "Action Approved"
              : state === "rejected"
                ? "Action Rejected"
                : state === "error"
                  ? "Approval Error"
                  : "Human-in-the-Loop Review"}
          </CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-4">
        {/* Action summary */}
        <div className="rounded-lg border border-border bg-muted/20 p-3 space-y-1">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
              Proposed Action
            </p>
            <Badge variant="warning" className="text-[10px]">HITL</Badge>
          </div>
          <code className="block text-sm font-mono text-foreground">{action}</code>
        </div>

        <div>
          <p className="mb-1 text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Reasoning
          </p>
          <p className="text-sm text-foreground/80">{reasoning}</p>
        </div>

        <div className="flex items-center justify-between rounded-lg border border-border bg-muted/20 px-3 py-2">
          <span className="text-sm text-muted-foreground">Estimated Impact</span>
          <span className="font-mono text-base font-bold text-foreground">
            RM {estimatedImpact.toLocaleString()}
          </span>
        </div>

        <Separator />

        <AnimatePresence mode="wait">
          {state === "idle" && (
            <motion.div
              key="idle"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -8 }}
              className="grid grid-cols-2 gap-3"
            >
              <Button
                variant="destructive"
                onClick={() => handleChoice("reject")}
                className="gap-2"
              >
                <XCircle className="h-4 w-4" />
                Reject
              </Button>
              <Button
                variant="success"
                onClick={() => handleChoice("approve")}
                className="gap-2"
              >
                <CheckCircle2 className="h-4 w-4" />
                Approve
              </Button>
            </motion.div>
          )}

          {state === "pending" && (
            <motion.div
              key="pending"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="flex items-center justify-center gap-2 py-2 text-sm text-muted-foreground"
            >
              <Loader2 className="h-4 w-4 animate-spin" />
              Submitting decision…
            </motion.div>
          )}

          {state === "approved" && (
            <motion.div
              key="approved"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
              className="flex items-center justify-center gap-2 py-2"
            >
              <CheckCircle2 className="h-5 w-5 text-emerald-400" />
              <span className="font-semibold text-emerald-300">
                {requiresApproval ? "Approved & dispatched" : "Auto-executed"}
              </span>
            </motion.div>
          )}

          {state === "rejected" && (
            <motion.div
              key="rejected"
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ type: "spring", stiffness: 200, damping: 20 }}
              className="flex items-center justify-center gap-2 py-2"
            >
              <XCircle className="h-5 w-5 text-red-400" />
              <span className="font-semibold text-red-300">Action rejected</span>
            </motion.div>
          )}

          {state === "error" && (
            <motion.div
              key="error"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="space-y-2"
            >
              <p className="text-sm text-red-300">{errorMsg}</p>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setState("idle")}
                className="w-full"
              >
                Retry
              </Button>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
