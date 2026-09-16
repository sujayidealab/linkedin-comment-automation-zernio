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

type Reply = {
  at?: string;
  commenter: string;
  comment: string;
  reply: string;
  commentId?: string;
};

type Status = {
  lastRunAt: string | null;
  lastError: string | null;
  enabled?: boolean;
  repliedCommentIds?: string[];
  recentReplies?: Reply[];
};

export default function Home() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) {
      setError("Could not load worker status.");
      return;
    }
    setStatus(await res.json());
    setError(null);
  }

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 10000);
    return () => clearInterval(id);
  }, []);

  async function run(dryRun: boolean) {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dryRun }),
      });
      const data = await res.json();
      if (!res.ok) setError(data.error || "Run failed");
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const replies = (status?.recentReplies || []).slice(0, 5);

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-medium text-zinc-500">Sujay Viston · LinkedIn</p>
        <h1 className="text-3xl font-semibold tracking-tight">Comment automation</h1>
        <p className="max-w-xl text-zinc-600">
          Every 2 minutes this replies to new comments on all of your LinkedIn
          posts. The last five replies it sent are listed below.
        </p>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Worker</CardTitle>
            <CardDescription>Zernio inbox · activity URN polling</CardDescription>
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
                  : "waiting"}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Handled</dt>
              <dd className="font-medium">
                {status?.repliedCommentIds?.length ?? 0}
              </dd>
            </div>
            <div>
              <dt className="text-zinc-500">Status</dt>
              <dd className="font-medium">
                {status?.enabled === false ? "paused" : "live"}
              </dd>
            </div>
          </dl>
          {status?.lastError ? (
            <p className="text-sm text-red-600">{status.lastError}</p>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
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
          <CardTitle>Last 5 replies</CardTitle>
          <CardDescription>
            Newest first. Each row is a comment the worker actually answered.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {replies.length === 0 ? (
            <p className="text-sm text-zinc-500">
              No replies yet. When someone comments, it will show up here.
            </p>
          ) : (
            <ol className="flex flex-col gap-4">
              {replies.map((item, index) => (
                <li
                  key={`${item.commentId || item.comment}-${item.at || index}`}
                  className="rounded-lg border border-zinc-200 bg-white p-4"
                >
                  <div className="mb-2 flex flex-wrap items-baseline justify-between gap-2 text-xs text-zinc-500">
                    <span className="font-medium text-zinc-800">
                      {index + 1}. {item.commenter}
                    </span>
                    <span>
                      {item.at ? new Date(item.at).toLocaleString() : ""}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-600">
                    <span className="font-medium text-zinc-500">They wrote: </span>
                    {item.comment}
                  </p>
                  <p className="mt-2 text-sm">
                    <span className="font-medium text-zinc-500">We replied: </span>
                    {item.reply}
                  </p>
                  {item.permalink ? (
                    <a
                      className="mt-2 inline-block text-xs text-zinc-500 underline"
                      href={item.permalink}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open post
                    </a>
                  ) : null}
                </li>
              ))}
            </ol>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
