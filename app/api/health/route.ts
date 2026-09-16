import { readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  const key = Boolean(process.env.ZERNIO_API_KEY);
  const file = path.join(process.cwd(), "data", "automation-state.json");
  let lastRunAt: string | null = null;
  let enabled = true;
  let handled = 0;
  try {
    const state = JSON.parse(await readFile(file, "utf8"));
    lastRunAt = state.lastRunAt ?? null;
    enabled = state.enabled !== false;
    handled = Array.isArray(state.repliedCommentIds)
      ? state.repliedCommentIds.length
      : 0;
  } catch {
    /* first boot */
  }
  return Response.json({
    ok: key,
    service: "linkedin-comment-automation",
    zernioKey: key,
    enabled,
    lastRunAt,
    handled,
    intervalSeconds: Number(process.env.COMMENT_AUTOMATION_INTERVAL_SECONDS || 30),
  });
}
