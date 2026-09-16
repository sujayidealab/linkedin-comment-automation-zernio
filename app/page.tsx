"use client";

import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

type Run = {
  at: string;
  dryRun?: boolean;
  queued: number;
  replied: number;
  errors?: string[];
  samples?: { commenter: string; comment: string; reply: string }[];
};

type Status = {
  lastRunAt: string | null;
  lastError: string | null;
  repliedCommentIds?: string[];
  runs?: Run[];
};

export default function Home() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function refresh() {
    const res = await fetch("/api/status", { cache: "no-store" });
    setStatus(await res.json());
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 15000);
    return () => clearInterval(id);
  }, []);

  async function run(dryRun: boolean) {
    setBusy(true);
    setMessage(null);
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dryRun }),
      });
      const data = await res.json();
      if (!res.ok) {
        setMessage(data.error || "Run failed");
      } else {
        setMessage(
          dryRun
            ? `Preview: ${data.queued} unanswered comments waiting.`
            : `Sent ${data.replied} replies (${data.queued} were queued).`,
        );
      }
      await refresh();
    } catch (err) {
      setMessage(String(err));
    } finally {
      setBusy(false);
    }
  }

  const latest = status?.runs?.[0];

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-medium text-zinc-500">Sujay Viston · LinkedIn</p>
        <h1 className="text-3xl font-semibold tracking-tight">
          Comment automation
        </h1>
        <p className="max-w-xl text-zinc-600">
          Every 2 minutes this watches every LinkedIn post on the connected
          Zernio account and replies to new top-level comments. It skips your
          own comments and threads you already answered.
        </p>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Live worker</CardTitle>
            <CardDescription>
              Cron interval is 120 seconds. Replies go out through Zernio inbox.
            </CardDescription>
          </div>
          <Badge variant="secondary">every 2 min</Badge>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-zinc-500">Last run</dt>
              <dd className="font-medium">
                {status?.lastRunAt
                  ? new Date(status.lastRunAt).toLocaleString()
                  : "waiting for first tick"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Comments already handled</dt>
              <dd className="font-medium">
                {status?.repliedCommentIds?.length ?? 0}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Last batch</dt>
              <dd className="font-medium">
                {latest
                  ? `${latest.replied} sent · ${latest.queued} seen`
                  : "—"}
              </dd>
            </div>
          </dl>
          {status?.lastError ? (
            <p className="text-sm text-red-600">{status.lastError}</p>
          ) : null}
          {message ? <p className="text-sm text-zinc-700">{message}</p> : null}
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => run(true)} disabled={busy} variant="outline">
              Preview unanswered
            </Button>
            <Button onClick={() => run(false)} disabled={busy}>
              Reply now
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recent activity</CardTitle>
          <CardDescription>
            Newest cron ticks. Preview rows do not post.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {(status?.runs || []).length === 0 ? (
            <p className="text-sm text-zinc-500">
              No runs yet. The 2-minute worker will fill this in.
            </p>
          ) : (
            (status?.runs || []).map((run) => (
              <div
                key={run.at}
                className="rounded-lg border border-zinc-200 bg-white p-3"
              >
                <div className="mb-2 flex items-center justify-between gap-2 text-sm">
                  <span className="font-medium">
                    {new Date(run.at).toLocaleString()}
                  </span>
                  <span className="text-zinc-500">
                    {run.dryRun ? "preview" : "live"} · queued {run.queued} ·
                    sent {run.replied}
                  </span>
                </div>
                <ul className="space-y-2 text-sm">
                  {(run.samples || []).map((sample, i) => (
                    <li key={i} className="border-t border-zinc-100 pt-2">
                      <p className="text-zinc-500">
                        {sample.commenter}: {sample.comment}
                      </p>
                      <p>{sample.reply}</p>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </main>
  );
}
