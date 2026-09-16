import { readFile } from "fs/promises";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  const file = path.join(process.cwd(), "data", "automation-state.json");
  try {
    const raw = await readFile(file, "utf8");
    return Response.json(JSON.parse(raw));
  } catch {
    return Response.json({
      repliedCommentIds: [],
      lastRunAt: null,
      runs: [],
      enabled: true,
    });
  }
}
