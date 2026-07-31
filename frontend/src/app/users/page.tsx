import type { Metadata } from "next";
import Link from "next/link";
import { Users } from "lucide-react";
import { UserManagement } from "@/components/nexusops/UserManagement";

export const metadata: Metadata = {
  title: "User Management — NexusFlow",
};

export default function UsersPage() {
  // In production, resolve the caller_id from the session/JWT.
  // For the portfolio demo we derive it from env or fall back to "dashboard_admin".
  const callerId = process.env.NEXT_PUBLIC_CALLER_ID ?? "dashboard_admin";

  return (
    <div className="mx-auto max-w-5xl space-y-6 p-6">
      <header className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Users className="h-7 w-7 text-primary" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">User Management</h1>
            <p className="text-sm text-muted-foreground">
              4-role RBAC — admin · operator · analyst · viewer
            </p>
          </div>
        </div>
        <Link
          href="/dashboard"
          className="rounded-lg border border-border px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground"
        >
          ← Control Tower
        </Link>
      </header>

      <UserManagement callerId={callerId} />
    </div>
  );
}
