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

// ─── Block Kit builders ───────────────────────────────────────────────────────

function helpBlocks(): object[] {
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
          "• `/nexus status` — Check system status\n\n" +
          "*HITL approvals* arrive as interactive messages. Use the *Approve* or *Reject* buttons directly in Slack.",
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
    const text = command.text?.trim();

    if (!text || text === "help") {
      await respond({ blocks: helpBlocks(), response_type: "ephemeral" });
      return;
    }

    if (text === "status") {
      try {
        const res = await fetch(`${apiBase}/status`);
        const data = (await res.json()) as Record<string, unknown>;
        await respond({ blocks: statusBlocks(data), response_type: "ephemeral" });
      } catch (e) {
        await respond({ text: `❌ Could not reach API: ${e}`, response_type: "ephemeral" });
      }
      return;
    }

    // Submit orchestration query
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
