import { readAutomationStatus } from "@/lib/automation-status";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET(request: Request) {
  const encoder = new TextEncoder();
  let lastFingerprint = "";
  let timer: ReturnType<typeof setInterval> | undefined;
  let closed = false;

  const stream = new ReadableStream({
    start(controller) {
      const safeEnqueue = (chunk: string) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(chunk));
        } catch {
          closed = true;
          if (timer) clearInterval(timer);
        }
      };
      const send = async (heartbeat = false) => {
        try {
          const state = await readAutomationStatus();
          const fingerprint = JSON.stringify({
            lastRunAt: state.lastRunAt,
            replies: state.recentReplies,
            handled: state.repliedCommentIds.length,
            enabled: state.enabled,
            lastError: state.lastError,
          });
          if (fingerprint === lastFingerprint) {
            if (heartbeat) safeEnqueue(": ping\n\n");
            return;
          }
          lastFingerprint = fingerprint;
          safeEnqueue(`data: ${JSON.stringify(state)}\n\n`);
        } catch {
          /* keep the stream open */
        }
      };
      void send();
      timer = setInterval(() => {
        void send(true);
      }, 2000);
      request.signal.addEventListener("abort", () => {
        closed = true;
        if (timer) clearInterval(timer);
        try {
          controller.close();
        } catch {
          /* already closed */
        }
      });
    },
    cancel() {
      closed = true;
      if (timer) clearInterval(timer);
    },
  });

  return new Response(stream, {
    headers: {
      "Content-Type": "text/event-stream; charset=utf-8",
      "Cache-Control": "no-cache, no-transform",
      Connection: "keep-alive",
      "X-Accel-Buffering": "no",
    },
  });
}
