"use client";

import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { AlertCircle, AlertTriangle, CheckCircle2, Info, Wifi, WifiOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useSSE } from "@/hooks/useSSE";

interface RegionMetrics {
  type: string;
  region: string;
  congestion: number;
  delivery_delay: number;
  avg_delivery_time: number;
  active_deliveries: number;
  active_incidents: number;
  last_updated: string;
}

interface Alert {
  id: string;
  region: string;
  severity: "critical" | "high" | "medium" | "info";
  message: string;
  congestion: number;
  incidents: number;
  timestamp: string;
}

function severityFromMetrics(m: RegionMetrics): Alert["severity"] {
  if (m.congestion >= 85 || m.active_incidents >= 4) return "critical";
  if (m.congestion >= 70 || m.active_incidents >= 2) return "high";
  if (m.congestion >= 55 || m.active_incidents >= 1) return "medium";
  return "info";
}

function messageFromMetrics(m: RegionMetrics): string {
  if (m.congestion >= 85) return `Critical congestion at ${m.congestion}% — route intervention needed`;
  if (m.congestion >= 70) return `Elevated congestion (${m.congestion}%) — ${m.active_incidents} incident(s) active`;
  if (m.congestion >= 55) return `Moderate delays, avg ${m.avg_delivery_time}h delivery time`;
  return `Operations nominal — ${m.active_deliveries} active deliveries`;
}

const SEVERITY_CONFIG = {
  critical: {
    icon: AlertCircle,
    color: "text-red-400",
    badge: "destructive" as const,
    border: "border-red-500/30",
    bg: "bg-red-950/10",
  },
  high: {
    icon: AlertTriangle,
    color: "text-orange-400",
    badge: "warning" as const,
    border: "border-orange-500/30",
    bg: "bg-orange-950/10",
  },
  medium: {
    icon: AlertTriangle,
    color: "text-yellow-400",
    badge: "warning" as const,
    border: "border-yellow-500/30",
    bg: "bg-yellow-950/10",
  },
  info: {
    icon: CheckCircle2,
    color: "text-emerald-400",
    badge: "success" as const,
    border: "border-emerald-500/20",
    bg: "bg-emerald-950/5",
  },
};

export function AlertList() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [seenRegions] = useState(() => new Map<string, string>());

  const { connected } = useSSE<RegionMetrics>({
    url: "/api/sse/metrics",
    onMessage: (m) => {
      const severity = severityFromMetrics(m);
      const key = `${m.region}-${severity}`;

      if (seenRegions.get(m.region) === key) return;
      seenRegions.set(m.region, key);

      const alert: Alert = {
        id: `${m.region}-${Date.now()}`,
        region: m.region,
        severity,
        message: messageFromMetrics(m),
        congestion: m.congestion,
        incidents: m.active_incidents,
        timestamp: m.last_updated,
      };

      setAlerts((prev) => {
        const filtered = prev.filter((a) => a.region !== m.region);
        return [alert, ...filtered].slice(0, 20);
      });
    },
  });

  const sorted = [...alerts].sort((a, b) => {
    const order = { critical: 0, high: 1, medium: 2, info: 3 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-base">Live Alerts</CardTitle>
          <div className="flex items-center gap-1.5">
            {connected ? (
              <Wifi className="h-3 w-3 text-emerald-400" />
            ) : (
              <WifiOff className="h-3 w-3 text-slate-500" />
            )}
            <span className="text-xs text-muted-foreground">
              {connected ? "Live" : "Connecting…"}
            </span>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {alerts.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            <div className="flex items-center gap-2">
              <Info className="h-4 w-4" />
              Awaiting metrics stream…
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            <AnimatePresence initial={false}>
              {sorted.map((alert) => {
                const cfg = SEVERITY_CONFIG[alert.severity];
                const Icon = cfg.icon;
                return (
                  <motion.li
                    key={alert.id}
                    initial={{ opacity: 0, x: -12 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.25 }}
                    className={`flex items-start gap-3 px-4 py-3 ${cfg.bg}`}
                  >
                    <Icon className={`mt-0.5 h-4 w-4 shrink-0 ${cfg.color}`} />
                    <div className="min-w-0 flex-1">
                      <div className="mb-1 flex items-center gap-2">
                        <span className="font-semibold text-slate-100">{alert.region}</span>
                        <Badge variant={cfg.badge} className="text-[10px]">
                          {alert.severity.toUpperCase()}
                        </Badge>
                        {alert.incidents > 0 && (
                          <Badge variant="outline" className="text-[10px]">
                            {alert.incidents} incident{alert.incidents !== 1 ? "s" : ""}
                          </Badge>
                        )}
                      </div>
                      <p className="truncate text-xs text-muted-foreground">{alert.message}</p>
                    </div>
                    <div className="shrink-0 text-right">
                      <div
                        className={`inline-block rounded px-1.5 py-0.5 font-mono text-xs font-bold ${
                          alert.congestion >= 85
                            ? "bg-red-500/20 text-red-300"
                            : alert.congestion >= 70
                              ? "bg-orange-500/20 text-orange-300"
                              : alert.congestion >= 55
                                ? "bg-yellow-500/20 text-yellow-300"
                                : "bg-emerald-500/20 text-emerald-300"
                        }`}
                      >
                        {alert.congestion}%
                      </div>
                    </div>
                  </motion.li>
                );
              })}
            </AnimatePresence>
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
