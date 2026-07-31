"use client";

import { useEffect, useState } from "react";
import { Loader2, Trash2, UserPlus } from "lucide-react";
import { apiFetch, getOrgId } from "@/lib/api";

interface SlackUser {
  id: string;
  slack_user_id: string;
  slack_username: string | null;
  role: string;
  added_by: string | null;
  org_id: string;
  created_at: string;
}

const ROLE_COLORS: Record<string, string> = {
  admin: "bg-red-500/20 text-red-300 border-red-500/30",
  operator: "bg-orange-500/20 text-orange-300 border-orange-500/30",
  analyst: "bg-blue-500/20 text-blue-300 border-blue-500/30",
  viewer: "bg-slate-500/20 text-slate-300 border-slate-500/30",
};

export function UserManagement({ callerId }: { callerId: string }) {
  const [users, setUsers] = useState<SlackUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ slack_user_id: "", role: "analyst" });
  const orgId = getOrgId();

  async function loadUsers() {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/slack/users?caller_id=${encodeURIComponent(callerId)}&org_id=${encodeURIComponent(orgId)}`);
      if (res.status === 403) { setError("Admin role required to manage users."); return; }
      if (!res.ok) throw new Error(`${res.status}`);
      setUsers(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { loadUsers(); }, [orgId]);

  async function addUser(e: React.FormEvent) {
    e.preventDefault();
    setAdding(true);
    try {
      const res = await apiFetch(`/api/slack/users?org_id=${encodeURIComponent(orgId)}`, {
        method: "POST",
        body: JSON.stringify({ ...form, caller_id: callerId }),
      });
      if (!res.ok) throw new Error(await res.text());
      setForm({ slack_user_id: "", role: "analyst" });
      await loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add user");
    } finally {
      setAdding(false);
    }
  }

  async function removeUser(slackUserId: string) {
    if (!confirm(`Remove ${slackUserId}?`)) return;
    try {
      const res = await apiFetch(`/api/slack/users/${encodeURIComponent(slackUserId)}`, {
        method: "DELETE",
        body: JSON.stringify({ caller_id: callerId }),
      });
      if (!res.ok) throw new Error(await res.text());
      await loadUsers();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove user");
    }
  }

  return (
    <div className="space-y-6">
      {/* Add user form */}
      <form
        onSubmit={addUser}
        className="flex flex-wrap gap-3 rounded-xl border border-border bg-card p-4"
      >
        <input
          required
          placeholder="Slack user ID (e.g. U012ABC)"
          value={form.slack_user_id}
          onChange={(e) => setForm((f) => ({ ...f, slack_user_id: e.target.value }))}
          className="flex-1 min-w-48 rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        />
        <select
          value={form.role}
          onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
          className="rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
        >
          {["admin", "operator", "analyst", "viewer"].map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button
          type="submit"
          disabled={adding}
          className="flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
        >
          {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <UserPlus className="h-4 w-4" />}
          Add user
        </button>
      </form>

      {error && (
        <p className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-red-300">
          {error}
        </p>
      )}

      {/* Users table */}
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="border-b border-border bg-muted/40">
            <tr>
              {["Slack user ID", "Username", "Role", "Added by", "Joined", ""].map((h) => (
                <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground uppercase tracking-wider">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {loading ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-muted-foreground">
                  <Loader2 className="mx-auto h-5 w-5 animate-spin" />
                </td>
              </tr>
            ) : users.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-muted-foreground text-sm">
                  No users registered for org <span className="font-mono">{orgId}</span>
                </td>
              </tr>
            ) : (
              users.map((u) => (
                <tr key={u.id} className="hover:bg-muted/20">
                  <td className="px-4 py-3 font-mono text-xs">{u.slack_user_id}</td>
                  <td className="px-4 py-3 text-muted-foreground">{u.slack_username ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-block rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${ROLE_COLORS[u.role] ?? "bg-slate-500/20 text-slate-300"}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{u.added_by ?? "—"}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      type="button"
                      onClick={() => removeUser(u.slack_user_id)}
                      className="rounded p-1 text-muted-foreground hover:text-destructive"
                      title="Remove user"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
