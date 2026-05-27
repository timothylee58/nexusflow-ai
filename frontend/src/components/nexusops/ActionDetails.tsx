"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  Activity,
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  Clock,
  Cpu,
  Target,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

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

interface ActionDetailsProps {
  result: OrchestrationResult;
  isLoading?: boolean;
}

const SEVERITY_BADGE: Record<string, "destructive" | "warning" | "default" | "success"> = {
  critical: "destructive",
  high: "warning",
  medium: "warning",
  low: "default",
  info: "success",
};

const STATUS_CONFIG: Record<string, { icon: typeof CheckCircle2; color: string; label: string }> = {
  completed: { icon: CheckCircle2, color: "text-emerald-400", label: "Completed" },
  executing: { icon: Activity, color: "text-blue-400", label: "Executing" },
  pending: { icon: Clock, color: "text-yellow-400", label: "Pending Approval" },
  rejected: { icon: AlertCircle, color: "text-red-400", label: "Rejected" },
  error: { icon: AlertCircle, color: "text-red-400", label: "Error" },
};

export function ActionDetails({ result, isLoading }: ActionDetailsProps) {
  const statusCfg = STATUS_CONFIG[result.execution_status] ?? STATUS_CONFIG.error;
  const StatusIcon = statusCfg.icon;

  return (
    <AnimatePresence mode="wait">
      {isLoading ? (
        <motion.div
          key="loading"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <Card>
            <CardContent className="p-6">
              <div className="space-y-3">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="animate-pulse space-y-2">
                    <div className="h-3 w-1/3 rounded bg-muted" />
                    <div className="h-4 rounded bg-muted/60" />
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </motion.div>
      ) : (
        <motion.div
          key={result.action_id ?? "result"}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          transition={{ duration: 0.3, ease: "easeOut" }}
        >
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Action Details</CardTitle>
                <div className="flex items-center gap-1.5">
                  <StatusIcon className={`h-4 w-4 ${statusCfg.color}`} />
                  <span className={`text-sm font-medium ${statusCfg.color}`}>
                    {statusCfg.label}
                  </span>
                </div>
              </div>
              {result.action_id && (
                <p className="font-mono text-xs text-muted-foreground">
                  ID: {result.action_id}
                </p>
              )}
            </CardHeader>

            <CardContent className="space-y-4">
              {/* Execution path */}
              {result.execution_path.length > 0 && (
                <div>
                  <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    Execution Path
                  </p>
                  <div className="flex flex-wrap items-center gap-1">
                    {result.execution_path.map((step, i) => (
                      <div key={step} className="flex items-center gap-1">
                        <motion.span
                          initial={{ opacity: 0, scale: 0.8 }}
                          animate={{ opacity: 1, scale: 1 }}
                          transition={{ delay: i * 0.07 }}
                          className="rounded bg-secondary px-2 py-0.5 font-mono text-xs text-foreground"
                        >
                          {step}
                        </motion.span>
                        {i < result.execution_path.length - 1 && (
                          <ChevronRight className="h-3 w-3 text-muted-foreground" />
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Parsed command */}
              {result.parsed_command && (
                <>
                  <Separator />
                  <div>
                    <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                      Parsed Command
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <Badge variant="outline">
                        <Cpu className="mr-1 h-3 w-3" />
                        {result.parsed_command.query_type}
                      </Badge>
                      <Badge variant="outline">{result.parsed_command.region}</Badge>
                      <Badge variant="outline">{result.parsed_command.metric}</Badge>
                      {result.llm_mode && (
                        <Badge variant="secondary">{result.llm_mode}</Badge>
                      )}
                    </div>
                  </div>
                </>
              )}

              {/* Analysis */}
              {result.analysis && (
                <>
                  <Separator />
                  <div>
                    <div className="mb-2 flex items-center justify-between">
                      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Analysis
                      </p>
                      <div className="flex items-center gap-2">
                        <Badge
                          variant={
                            SEVERITY_BADGE[result.analysis.severity] ?? "default"
                          }
                        >
                          {result.analysis.severity.toUpperCase()}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {Math.round(result.analysis.confidence * 100)}% confidence
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-foreground">{result.analysis.summary}</p>
                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-secondary">
                      <motion.div
                        initial={{ width: 0 }}
                        animate={{ width: `${result.analysis.confidence * 100}%` }}
                        transition={{ duration: 0.6, ease: "easeOut" }}
                        className="h-full rounded-full bg-primary"
                      />
                    </div>
                  </div>
                </>
              )}

              {/* Decision */}
              {result.decision && (
                <>
                  <Separator />
                  <div>
                    <div className="mb-2 flex items-center gap-2">
                      <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
                        Decision
                      </p>
                      {result.decision.requires_approval ? (
                        <AlertTriangle className="h-3.5 w-3.5 text-orange-400" />
                      ) : (
                        <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
                      )}
                    </div>
                    <div className="rounded-lg border border-border bg-muted/30 p-3 space-y-2">
                      <div className="flex items-center gap-2">
                        <Target className="h-4 w-4 shrink-0 text-muted-foreground" />
                        <code className="text-sm font-mono text-foreground">
                          {result.decision.target_action}
                        </code>
                      </div>
                      <p className="text-xs text-muted-foreground">{result.decision.reasoning}</p>
                      <div className="flex items-center justify-between pt-1">
                        <span className="text-xs text-muted-foreground">Estimated impact</span>
                        <span className="font-mono text-sm font-semibold text-foreground">
                          RM {result.decision.estimated_impact.toLocaleString()}
                        </span>
                      </div>
                    </div>
                  </div>
                </>
              )}

              {/* Errors */}
              {result.errors && result.errors.length > 0 && (
                <>
                  <Separator />
                  <div className="rounded-lg border border-destructive/40 bg-destructive/10 p-3">
                    <div className="mb-1 flex items-center gap-1.5 text-sm font-medium text-red-300">
                      <AlertCircle className="h-4 w-4" />
                      Errors
                    </div>
                    <ul className="space-y-1">
                      {result.errors.map((e, i) => (
                        <li key={i} className="text-xs text-red-200/80">
                          {e}
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
