import { readAutomationStatus } from "@/lib/automation-status";

export const dynamic = "force-dynamic";

export async function GET() {
  const state = await readAutomationStatus();
  return Response.json(state, {
    headers: {
      "Cache-Control": "no-store, no-cache, must-revalidate",
    },
  });
}
