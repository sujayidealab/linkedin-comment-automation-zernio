import { readAutomationStatus } from "@/lib/automation-status";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

export async function GET() {
  const encoder = new TextEncoder();
  let lastFingerprint = "";
  let timer: ReturnType<typeof setInterval> | undefined;

  const stream = new ReadableStream({
    start(controller) {
      const send = async () => {
        try {
          const state = await readAutomationStatus();
          const fingerprint = JSON.stringify({
            lastRunAt: state.lastRunAt,
            replies: state.recentReplies,
            handled: state.repliedCommentIds.length,
            enabled: state.enabled,
            lastError: state.lastError,
          });
          if (fingerprint === lastFingerprint) return;
          lastFingerprint = fingerprint;
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(state)}\n\n`));
        } catch {
          /* keep the stream open */
        }
      };
      void send();
      timer = setInterval(() => {
        void send();
      }, 2000);
    },
    cancel() {
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
