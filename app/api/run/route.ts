import type { NextRequest } from "next/server";
import { spawn } from "child_process";
import path from "path";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function pythonOnce(extra: string[] = []): Promise<{ code: number; stdout: string; stderr: string }> {
  const script = path.join(process.cwd(), "scripts", "linkedin_comment_cron.py");
  return new Promise((resolve) => {
    const child = spawn("python3", [script, "--once", ...extra], {
      cwd: process.cwd(),
      env: process.env,
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("close", (code) => resolve({ code: code ?? 1, stdout, stderr }));
  });
}

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const extra = body.dryRun ? ["--dry-run"] : [];
  const result = await pythonOnce(extra);
  try {
    return Response.json(JSON.parse(result.stdout));
  } catch {
    return Response.json(
      { ok: false, error: result.stderr || result.stdout || "cron failed", code: result.code },
      { status: 500 },
    );
  }
}
