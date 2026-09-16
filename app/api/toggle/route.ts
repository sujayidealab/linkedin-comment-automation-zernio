import { NextRequest } from "next/server";
import { runPython } from "@/lib/python";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => ({}));
  const enabled = Boolean(body.enabled);
  try {
    const data = await runPython([enabled ? "--enable" : "--pause"]);
    return Response.json(data);
  } catch (error) {
    return Response.json(
      { ok: false, error: error instanceof Error ? error.message : "toggle failed" },
      { status: 500 },
    );
  }
}
