import { readFile } from "fs/promises";
import path from "path";

export type ReplyRow = {
  at?: string;
  commenter: string;
  comment: string;
  reply: string;
  commentId?: string;
  permalink?: string;
};

export type AutomationStatus = {
  lastRunAt: string | null;
  lastError: string | null;
  enabled: boolean;
  repliedCommentIds: string[];
  recentReplies: ReplyRow[];
  runs: unknown[];
};

type RunSample = {
  commenter?: string;
  comment?: string;
  reply?: string;
  commentId?: string;
};

type RunRow = {
  at?: string;
  dryRun?: boolean;
  replied?: number;
  samples?: RunSample[];
};

function repliesFromRuns(runs: RunRow[]): ReplyRow[] {
  const out: ReplyRow[] = [];
  const seen = new Set<string>();
  for (const run of runs) {
    if (run.dryRun || !run.replied) continue;
    for (const sample of run.samples || []) {
      const key = `${sample.commentId || ""}|${sample.comment || ""}|${sample.reply || ""}`;
      if (seen.has(key)) continue;
      seen.add(key);
      out.push({
        at: run.at,
        commenter: sample.commenter || "someone",
        comment: sample.comment || "",
        reply: sample.reply || "",
        commentId: sample.commentId,
      });
      if (out.length >= 5) return out;
    }
  }
  return out.slice(0, 5);
}

export async function readAutomationStatus(): Promise<AutomationStatus> {
  const file = path.join(process.cwd(), "data", "automation-state.json");
  try {
    const raw = await readFile(file, "utf8");
    const state = JSON.parse(raw) as {
      lastRunAt?: string | null;
      lastError?: string | null;
      enabled?: boolean;
      repliedCommentIds?: string[];
      recentReplies?: ReplyRow[];
      runs?: RunRow[];
    };
    const stored = Array.isArray(state.recentReplies) ? state.recentReplies : [];
    const fromRuns = repliesFromRuns(state.runs || []);
    const storedStamp = stored[0]?.at ? Date.parse(stored[0].at) : 0;
    const runStamp = fromRuns[0]?.at ? Date.parse(fromRuns[0].at) : 0;
    const recentReplies = runStamp > storedStamp ? fromRuns : stored.slice(0, 5);
    return {
      lastRunAt: state.lastRunAt ?? null,
      lastError: state.lastError ?? null,
      enabled: state.enabled !== false,
      repliedCommentIds: state.repliedCommentIds || [],
      recentReplies: recentReplies.length ? recentReplies : fromRuns,
      runs: state.runs || [],
    };
  } catch {
    return {
      lastRunAt: null,
      lastError: null,
      enabled: true,
      repliedCommentIds: [],
      recentReplies: [],
      runs: [],
    };
  }
}
