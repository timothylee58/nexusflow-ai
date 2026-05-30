import "dotenv/config";
import { App, BlockAction, ButtonAction } from "@slack/bolt";

const token = process.env.SLACK_BOT_TOKEN;
const signingSecret = process.env.SLACK_SIGNING_SECRET;
const apiBase = process.env.NEXUSFLOW_API_URL ?? "http://backend:8000";

// ─── helpers ──────────────────────────────────────────────────────────────────

async function apiPost(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function apiGet(path: string): Promise<unknown> {
  const res = await fetch(`${apiBase}${path}`);
  if (!res.ok) throw new Error(`API ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

async function apiDelete(path: string, body: unknown): Promise<unknown> {
  const res = await fetch(`${apiBase}${path}`, {
    method: "DELETE",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}: ${await res.text()}`);
  return res.json();
}

// ─── RBAC ────────────────────────────────────────────────────────────────────

type UserRole = "admin" | "analyst" | null;

interface RoleCheck {
  slack_user_id: string;
  role: UserRole;
  source: "bootstrap" | "db" | null;
  slack_username?: string;
}

async function getUserRole(userId: string): Promise<RoleCheck> {
  const data = (await apiGet(
    `/slack/users/check?slack_user_id=${encodeURIComponent(userId)}`,
  )) as RoleCheck;
  return data;
}

/**
 * Return true when the user holds at least one of the required roles.
 * On API errors, defaults to deny.
 */
async function isAuthorized(userId: string, requiredRoles: UserRole[]): Promise<boolean> {
  try {
    const { role } = await getUserRole(userId);
    return role !== null && requiredRoles.includes(role);
  } catch {
    return false;
  }
}

function unauthorizedBlocks(requiredRole: string): object[] {
  return [
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `🔒 *Access denied.* This action requires the *${requiredRole}* role.\nAsk an admin to run \`/nexus users add @you ${requiredRole}\`.`,
      },
    },
  ];
}

// ─── Block Kit builders ───────────────────────────────────────────────────────

function helpBlocks(isAdmin: boolean): object[] {
  const adminSection = isAdmin
    ? "\n\n*Admin commands:*\n" +
      "• `/nexus users` — List registered users\n" +
      "• `/nexus users add @user [admin|analyst]` — Grant access\n" +
      "• `/nexus users remove @user` — Revoke access"
    : "";
  return [
    {
      type: "header",
      text: { type: "plain_text", text: "🌐 NexusFlow AI — Help" },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text:
          "*Available commands:*\n" +
          "• `/nexus <query>` — Submit a natural language ops query\n" +
          "  _Example: `/nexus Show KL bottlenecks right now`_\n" +
          "• `/nexus status` — Check system status\n" +
          "• `/nexus whoami` — Show your role\n" +
          "*HITL approvals* arrive as interactive messages. Use the *Approve* or *Reject* buttons directly in Slack." +
          adminSection,
      },
    },
  ];
}

function statusBlocks(data: Record<string, unknown>): object[] {
  const slackConfigured = data.slack_configured ? "✅ Connected" : "⚠️ Not configured";
  const llmConfigured = data.llm_configured ? `✅ ${data.llm_provider}` : "⚠️ Not configured";
  return [
    {
      type: "header",
      text: { type: "plain_text", text: "🔧 NexusFlow System Status" },
    },
    {
      type: "section",
      fields: [
        { type: "mrkdwn", text: `*Slack Bot:*\n${slackConfigured}` },
        { type: "mrkdwn", text: `*LLM:*\n${llmConfigured}` },
        { type: "mrkdwn", text: `*Environment:*\n${data.environment ?? "unknown"}` },
        {
          type: "mrkdwn",
          text: `*HITL Timeout:*\n${data.hitl_timeout_minutes ?? 30} min`,
        },
      ],
    },
  ];
}

function orchestrationResultBlocks(result: Record<string, unknown>): object[] {
  const analysis = result.analysis as Record<string, unknown> | undefined;
  const decision = result.decision as Record<string, unknown> | undefined;
  const path = (result.execution_path as string[] | undefined)?.join(" → ") ?? "";

  const severityEmoji: Record<string, string> = {
    critical: "🔴",
    high: "🟠",
    medium: "🟡",
    low: "🟢",
  };
  const emoji = severityEmoji[(analysis?.severity as string) ?? ""] ?? "⚪";

  const blocks: object[] = [
    {
      type: "header",
      text: {
        type: "plain_text",
        text: `${emoji} NexusFlow Analysis — ${(analysis?.severity as string ?? "").toUpperCase()}`,
      },
    },
    {
      type: "section",
      text: {
        type: "mrkdwn",
        text: `*Summary:*\n${analysis?.summary ?? "—"}`,
      },
    },
  ];

  if (decision) {
    blocks.push({
      type: "section",
      fields: [
        { type: "mrkdwn", text: `*Action:*\n\`${decision.target_action}\`` },
        {
          type: "mrkdwn",
          text: `*Est. Impact:*\nRM ${Number(decision.estimated_impact).toLocaleString()}`,
        },
        {
          type: "mrkdwn",
          text: `*Approval:*\n${decision.requires_approval ? "Required (HITL)" : "Auto-executed"}`,
        },
        { type: "mrkdwn", text: `*Status:*\n${result.execution_status}` },
      ],
    });
  }

  if (path) {
    blocks.push({
      type: "context",
      elements: [{ type: "mrkdwn", text: `Path: ${path} · mode: ${result.llm_mode ?? "—"}` }],
    });
  }

  return blocks;
}

interface UserRecord {
  id: string;
  slack_user_id: string;
  slack_username: string | null;
  role: string;
  added_by: string | null;
  created_at: string;
}

function usersListBlocks(users: UserRecord[]): object[] {
  if (users.length === 0) {
    return [
      {
        type: "section",
        text: { type: "mrkdwn", text: "_No registered users yet._" },
      },
    ];
  }
  const rows = users
    .map((u) => {
      const name = u.slack_username ? `@${u.slack_username}` : u.slack_user_id;
      return `• ${name} — \`${u.role}\``;
    })
    .join("\n");
  return [
    { type: "header", text: { type: "plain_text", text: "👥 Registered Users" } },
    { type: "section", text: { type: "mrkdwn", text: rows } },
  ];
}

// ─── Bolt app ─────────────────────────────────────────────────────────────────

async function main() {
  if (!token || !signingSecret) {
    console.warn(
      "[slack-bot] SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET required. Idling.",
    );
    setInterval(() => {}, 1 << 30);
    return;
  }

  const appToken = process.env.SLACK_APP_LEVEL_TOKEN;
  const app = new App({
    token,
    signingSecret,
    ...(appToken ? { appToken, socketMode: true as const } : {}),
  });

  // ── /nexus slash command ──────────────────────────────────────────────────

  app.command("/nexus", async ({ command, ack, respond }) => {
    await ack();
    const userId = command.user_id;
    const text = command.text?.trim() ?? "";

    // ── whoami ────────────────────────────────────────────────────────────
    if (text === "whoami") {
      try {
        const info = await getUserRole(userId);
        const role = info.role ?? "none (not registered)";
        const src = info.source ? ` _(${info.source})_` : "";
        await respond({
          text: `🪪 You are <@${userId}>. Role: *${role}*${src}`,
          response_type: "ephemeral",
        });
      } catch (e) {
        await respond({ text: `❌ Could not reach API: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // ── users list ────────────────────────────────────────────────────────
    if (text === "users") {
      if (!(await isAuthorized(userId, ["admin"]))) {
        await respond({ blocks: unauthorizedBlocks("admin"), response_type: "ephemeral" });
        return;
      }
      try {
        const users = (await apiGet(
          `/slack/users?caller_id=${encodeURIComponent(userId)}`,
        )) as UserRecord[];
        await respond({ blocks: usersListBlocks(users), response_type: "ephemeral" });
      } catch (e) {
        await respond({ text: `❌ Failed to list users: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // ── users add @mention role ───────────────────────────────────────────
    const addMatch = text.match(/^users\s+add\s+<@([A-Z0-9]+)(?:\|[^>]+)?>\s*(admin|analyst)?$/i);
    if (addMatch) {
      if (!(await isAuthorized(userId, ["admin"]))) {
        await respond({ blocks: unauthorizedBlocks("admin"), response_type: "ephemeral" });
        return;
      }
      const targetId = addMatch[1];
      const role = (addMatch[2]?.toLowerCase() ?? "analyst") as "admin" | "analyst";
      try {
        await apiPost("/slack/users", {
          slack_user_id: targetId,
          role,
          caller_id: userId,
        });
        await respond({
          text: `✅ <@${targetId}> registered as *${role}*.`,
          response_type: "ephemeral",
        });
      } catch (e) {
        await respond({ text: `❌ Failed to add user: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // ── users remove @mention ─────────────────────────────────────────────
    const removeMatch = text.match(/^users\s+remove\s+<@([A-Z0-9]+)(?:\|[^>]+)?>/i);
    if (removeMatch) {
      if (!(await isAuthorized(userId, ["admin"]))) {
        await respond({ blocks: unauthorizedBlocks("admin"), response_type: "ephemeral" });
        return;
      }
      const targetId = removeMatch[1];
      try {
        await apiDelete(`/slack/users/${encodeURIComponent(targetId)}`, { caller_id: userId });
        await respond({
          text: `✅ <@${targetId}> removed from the registry.`,
          response_type: "ephemeral",
        });
      } catch (e) {
        await respond({ text: `❌ Failed to remove user: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // ── help / status (open to registered users) ──────────────────────────
    if (!text || text === "help") {
      const roleInfo = await getUserRole(userId).catch(() => ({ role: null }));
      await respond({
        blocks: helpBlocks(roleInfo.role === "admin"),
        response_type: "ephemeral",
      });
      return;
    }

    if (text === "status") {
      // status is intentionally open (read-only, non-sensitive)
      try {
        const res = await fetch(`${apiBase}/status`);
        const data = (await res.json()) as Record<string, unknown>;
        await respond({ blocks: statusBlocks(data), response_type: "ephemeral" });
      } catch (e) {
        await respond({ text: `❌ Could not reach API: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // ── natural language query — requires analyst or admin ────────────────
    if (!(await isAuthorized(userId, ["admin", "analyst"]))) {
      await respond({ blocks: unauthorizedBlocks("analyst"), response_type: "ephemeral" });
      return;
    }

    await respond({
      text: `⏳ Processing: _${text}_`,
      response_type: "in_channel",
    });

    try {
      const result = (await apiPost("/agent/orchestrate", {
        query: text,
        user_id: command.user_id,
      })) as Record<string, unknown>;

      await respond({
        blocks: orchestrationResultBlocks(result),
        response_type: "in_channel",
        replace_original: true,
      });
    } catch (e) {
      await respond({
        text: `❌ Orchestration failed: ${e}`,
        response_type: "in_channel",
        replace_original: true,
      });
    }
  });

  // ── HITL button actions (Socket Mode path) ───────────────────────────────
  // In HTTP mode these are handled by the FastAPI /slack/interactions endpoint.
  // In Socket Mode, Slack delivers interactions here via the WebSocket tunnel.

  async function handleHitlAction(
    actionId: "hitl_approve" | "hitl_reject",
    buttonValue: string,
    userId: string,
    userName: string,
    ack: () => Promise<void>,
    respond: (msg: object) => Promise<void>,
  ) {
    await ack();

    // HITL decisions are admin-only
    if (!(await isAuthorized(userId, ["admin"]))) {
      await respond({
        replace_original: false,
        text: "🔒 *Access denied.* Only admins can approve or reject HITL decisions.",
      });
      return;
    }

    const choice = actionId === "hitl_approve" ? "approve" : "reject";
    const verb = choice === "approve" ? "approved" : "rejected";

    try {
      const result = (await apiPost("/agent/hitl/approve", {
        decision_id: buttonValue,
        approval_choice: choice,
        user_id: userName || userId,
        notes: `${verb.charAt(0).toUpperCase() + verb.slice(1)} via Slack (Socket Mode) by ${userName || userId}`,
      })) as Record<string, unknown>;

      const icon = choice === "approve" ? "✅" : "❌";
      await respond({
        replace_original: true,
        text: `${icon} *${verb.charAt(0).toUpperCase() + verb.slice(1)}* by <@${userId}> — status: \`${result.status}\``,
      });
    } catch (e) {
      await respond({
        replace_original: false,
        text: `❌ HITL action failed: ${e}`,
      });
    }
  }

  app.action<BlockAction<ButtonAction>>(
    "hitl_approve",
    async ({ action, body, ack, respond }) => {
      await handleHitlAction(
        "hitl_approve",
        action.value ?? "",
        body.user.id,
        body.user.username ?? body.user.name ?? body.user.id,
        ack,
        respond,
      );
    },
  );

  app.action<BlockAction<ButtonAction>>(
    "hitl_reject",
    async ({ action, body, ack, respond }) => {
      await handleHitlAction(
        "hitl_reject",
        action.value ?? "",
        body.user.id,
        body.user.username ?? body.user.name ?? body.user.id,
        ack,
        respond,
      );
    },
  );

  // ── Direct message echo ───────────────────────────────────────────────────

  app.message(async ({ message, say }) => {
    if (message.subtype !== undefined || !("text" in message)) return;
    await say(
      `Use \`/nexus <query>\` to submit an operations command, or \`/nexus help\` for guidance.`,
    );
  });

  await app.start(process.env.PORT ? Number(process.env.PORT) : 3001);
  console.log(`[slack-bot] Bolt app running on port ${process.env.PORT ?? 3001}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
