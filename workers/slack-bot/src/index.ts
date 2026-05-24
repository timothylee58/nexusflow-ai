import "dotenv/config";
import { App } from "@slack/bolt";

const token = process.env.SLACK_BOT_TOKEN;
const signingSecret = process.env.SLACK_SIGNING_SECRET;

async function main() {
  if (!token || !signingSecret) {
    console.warn(
      "[slack-bot] SLACK_BOT_TOKEN and SLACK_SIGNING_SECRET are required for Bolt. Idling for Docker bootstrap.",
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

  app.message(async ({ message, say }) => {
    if (message.subtype !== undefined || !("text" in message)) return;
    await say(`Echo: ${message.text}`);
  });

  await app.start(process.env.PORT ? Number(process.env.PORT) : 3001);
  console.log("[slack-bot] Bolt app running");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
