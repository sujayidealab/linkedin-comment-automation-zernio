import { readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  const file = path.join(process.cwd(), "data", "automation-state.json");
  try {
    const raw = await readFile(file, "utf8");
    const state = JSON.parse(raw);
    if (!Array.isArray(state.recentReplies) || state.recentReplies.length === 0) {
      const replies: unknown[] = [];
      for (const run of state.runs || []) {
        if (run.dryRun || !run.replied) continue;
        for (const sample of run.samples || []) {
          replies.push({ at: run.at, ...sample });
          if (replies.length >= 5) break;
        }
        if (replies.length >= 5) break;
      }
      state.recentReplies = replies;
    } else {
      state.recentReplies = state.recentReplies.slice(0, 5);
    }
    return Response.json(state);
  } catch {
    return Response.json({
      repliedCommentIds: [],
      lastRunAt: null,
      runs: [],
      enabled: true,
      recentReplies: [],
    });
  }
}
