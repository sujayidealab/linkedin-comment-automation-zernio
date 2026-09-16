import { spawn } from "child_process";
import path from "path";

export function runPython(args: string[], timeoutMs = 60000): Promise<Record<string, unknown>> {
  const script = path.join(process.cwd(), "scripts", "linkedin_comment_cron.py");
  return new Promise((resolve, reject) => {
    const child = spawn("python3", [script, ...args], {
      cwd: process.cwd(),
      env: process.env,
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
