import { spawn } from "child_process";
import { readFileSync } from "fs";
import path from "path";

function envWithDotenv(): NodeJS.ProcessEnv {
  const env = { ...process.env };
  try {
    const text = readFileSync(path.join(process.cwd(), ".env"), "utf8");
    for (const line of text.split("\n")) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
      const eq = trimmed.indexOf("=");
      const key = trimmed.slice(0, eq).trim();
      let value = trimmed.slice(eq + 1).trim();
      if (
        (value.startsWith('"') && value.endsWith('"')) ||
        (value.startsWith("'") && value.endsWith("'"))
      ) {
        value = value.slice(1, -1);
      }
      if (!(key in env) || !env[key]) env[key] = value;
    }
  } catch {
    /* .env is optional when the process already has keys */
  }
  return env;
}

export function runPython(args: string[], timeoutMs = 90000): Promise<Record<string, unknown>> {
  const script = path.join(process.cwd(), "scripts", "linkedin_comment_cron.py");
  return new Promise((resolve, reject) => {
    const child = spawn("python3", [script, ...args], {
      cwd: process.cwd(),
      env: envWithDotenv(),
    });
    let stdout = "";
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill("SIGKILL");
      reject(new Error("Timed out talking to the comment worker"));
    }, timeoutMs);
    child.stdout.on("data", (d) => {
      stdout += d.toString();
    });
    child.stderr.on("data", (d) => {
      stderr += d.toString();
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      const start = stdout.indexOf("{");
      const end = stdout.lastIndexOf("}");
      if (start >= 0 && end > start) {
        try {
          resolve(JSON.parse(stdout.slice(start, end + 1)));
          return;
        } catch {
          /* fall through */
        }
      }
      reject(
        new Error(stderr.trim() || stdout.trim() || `worker exited ${code ?? "?"}`),
      );
    });
  });
}
