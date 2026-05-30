"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { LayoutDashboard, Slack } from "lucide-react";
import { ControlTowerDashboard } from "@/components/control-tower/control-tower-dashboard";
import { SlackSettings } from "@/components/nexusops/SlackSettings";
import { cn } from "@/lib/utils";

type Tab = "dashboard" | "slack";

const TABS: { id: Tab; label: string; icon: typeof LayoutDashboard }[] = [
  { id: "dashboard", label: "Control Tower", icon: LayoutDashboard },
  { id: "slack", label: "Slack & HITL", icon: Slack },
];

export default function DashboardPage() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="flex min-h-screen flex-col">
      {/* Top navigation */}
      <nav className="sticky top-0 z-10 border-b border-border bg-background/90 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center gap-1 px-6 py-2">
          <span className="mr-4 text-sm font-semibold tracking-tight text-foreground">
            NexusFlow
          </span>
          {TABS.map((t) => {
            const Icon = t.icon;
            const active = tab === t.id;
            return (
              <button
                key={t.id}
                type="button"
                onClick={() => setTab(t.id)}
                className={cn(
                  "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                  active
                    ? "bg-secondary text-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                <Icon className="h-4 w-4" />
                {t.label}
              </button>
            );
          })}
        </div>
      </nav>

      {/* Tab content */}
      <main className="flex-1">
        {tab === "dashboard" && <ControlTowerDashboard />}
        {tab === "slack" && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mx-auto max-w-4xl p-6"
          >
            <SlackSettings />
          </motion.div>
        )}
      </main>
    </div>
  );
}
