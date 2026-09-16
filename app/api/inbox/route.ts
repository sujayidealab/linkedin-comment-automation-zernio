import { runPython } from "@/lib/python";

export const dynamic = "force-dynamic";
export const maxDuration = 60;

export async function GET() {
  try {
    const data = await runPython(["--snapshot"]);
    return Response.json(data);
  } catch (error) {
    return Response.json(
      { ok: false, error: error instanceof Error ? error.message : "snapshot failed" },
      { status: 502 },
    );
  }
}
