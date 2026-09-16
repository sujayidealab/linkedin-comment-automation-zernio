"use client";

import { useCallback, useEffect, useState } from "react";
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
  permalink?: string;
};

type Target = {
  commenter?: string;
  commentText?: string;
  comment?: string;
  reply?: string;
  permalink?: string;
  postPreview?: string;
};

type Status = {
  lastRunAt: string | null;
  lastError: string | null;
  enabled?: boolean;
  repliedCommentIds?: string[];
  recentReplies?: Reply[];
};

type ActionNote = {
  tone: "ok" | "warn" | "err";
  text: string;
};

export default function Home() {
  const [status, setStatus] = useState<Status | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<ActionNote | null>(null);
  const [liveAt, setLiveAt] = useState<number | null>(null);
  const [preview, setPreview] = useState<Target[]>([]);

  const applyStatus = useCallback((next: Status) => {
    setStatus(next);
    setLiveAt(Date.now());
  }, []);

  const refresh = useCallback(async () => {
    const res = await fetch("/api/status", { cache: "no-store" });
    if (!res.ok) {
      setError("Could not load worker status.");
      return;
    }
    applyStatus(await res.json());
    setError(null);
  }, [applyStatus]);

  useEffect(() => {
    void refresh();
    const poll = setInterval(() => {
      void refresh();
    }, 3000);

    const source = new EventSource("/api/replies/stream");
    source.onmessage = (event) => {
      try {
        applyStatus(JSON.parse(event.data) as Status);
      } catch {
        /* ignore a bad chunk */
      }
    };

    return () => {
      clearInterval(poll);
      source.close();
    };
  }, [applyStatus, refresh]);

  async function run(dryRun: boolean) {
    const label = dryRun ? "preview" : "reply";
    setBusy(label);
    setError(null);
    setNote(null);
    try {
      const res = await fetch("/api/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ dryRun }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Run failed");
        return;
      }
      const targets = (data.targets || []) as Target[];
      if (dryRun) {
        setPreview(targets);
        const n = Number(data.queued || targets.length || 0);
        setNote({
          tone: n ? "warn" : "ok",
          text: n
            ? `${n} unanswered comment${n === 1 ? "" : "s"} ready to reply.`
            : "Inbox is caught up — nothing waiting.",
        });
      } else {
        const n = Number(data.replied || 0);
        const errs = Array.isArray(data.errors) ? data.errors.length : 0;
        setPreview([]);
        setNote({
          tone: errs ? "err" : "ok",
          text:
            n > 0
              ? `Sent ${n} reply${n === 1 ? "" : "ies"}${errs ? ` (${errs} failed)` : ""}.`
              : errs
                ? `No replies sent (${errs} error${errs === 1 ? "" : "s"}).`
                : "No new comments to answer.",
        });
      }
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  async function toggleEnabled() {
    const next = status?.enabled === false;
    setBusy("toggle");
    setError(null);
    try {
      const res = await fetch("/api/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled: next }),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.error || "Could not change worker status");
        return;
      }
      setNote({
        tone: "ok",
        text: next ? "Worker resumed. It will reply on the next pass." : "Worker paused. No auto-replies until you resume.",
      });
      await refresh();
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  async function refreshNow() {
    setBusy("refresh");
    setError(null);
    try {
      await refresh();
      setNote({ tone: "ok", text: "Status reloaded from the worker." });
    } finally {
      setBusy(null);
    }
  }

  const replies = (status?.recentReplies || []).slice(0, 5);
  const paused = status?.enabled === false;

  return (
    <main className="mx-auto flex w-full max-w-3xl flex-col gap-6 px-4 py-10">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-medium text-zinc-500">Sujay Viston · LinkedIn</p>
        <h1 className="text-3xl font-semibold tracking-tight">Comment automation</h1>
        <p className="max-w-xl text-zinc-600">
          The worker checks every 30 seconds and replies to new comments on your
          LinkedIn posts. The last five replies below refresh on their own.
        </p>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div>
            <CardTitle>Worker</CardTitle>
            <CardDescription>Zernio inbox · activity URN polling</CardDescription>
          </div>
          <Badge variant="secondary">{paused ? "paused" : "live · 30s"}</Badge>
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
              <dd className="font-medium">{paused ? "paused" : "live"}</dd>
            </div>
          </dl>
          {status?.lastError ? (
            <p className="text-sm text-red-600">{status.lastError}</p>
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          {note ? (
            <p
              className={
                note.tone === "err"
                  ? "text-sm text-red-600"
                  : note.tone === "warn"
                    ? "text-sm text-amber-700"
                    : "text-sm text-zinc-700"
              }
            >
              {note.text}
            </p>
          ) : null}
          <div className="flex flex-wrap gap-2">
            <Button
              type="button"
              nativeButton
              onClick={() => void refreshNow()}
              disabled={Boolean(busy)}
              variant="outline"
            >
              {busy === "refresh" ? "Refreshing…" : "Refresh"}
            </Button>
            <Button
              type="button"
              nativeButton
              onClick={() => void toggleEnabled()}
              disabled={Boolean(busy)}
              variant="outline"
            >
              {busy === "toggle"
                ? "Updating…"
                : paused
                  ? "Resume worker"
                  : "Pause worker"}
            </Button>
            <Button
              type="button"
              nativeButton
              onClick={() => void run(true)}
              disabled={Boolean(busy)}
              variant="outline"
            >
              {busy === "preview" ? "Checking inbox…" : "Preview unanswered"}
            </Button>
            <Button
              type="button"
              nativeButton
              onClick={() => void run(false)}
              disabled={Boolean(busy) || paused}
            >
              {busy === "reply" ? "Sending replies…" : "Reply now"}
            </Button>
          </div>
        </CardContent>
      </Card>

      {preview.length > 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>Unanswered preview</CardTitle>
            <CardDescription>
              What Reply now will send. Nothing has been posted yet.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="flex flex-col gap-4">
              {preview.map((item, index) => (
                <li
                  key={`${item.commenter}-${item.commentText || item.comment}-${index}`}
                  className="rounded-lg border border-zinc-200 bg-white p-4"
                >
                  <p className="text-sm font-medium text-zinc-800">
                    {index + 1}. {item.commenter || "someone"}
                  </p>
                  <p className="mt-1 text-sm text-zinc-600">
                    {(item.commentText || item.comment || "").trim()}
                  </p>
                  <p className="mt-2 text-sm">
                    <span className="font-medium text-zinc-500">Draft: </span>
                    {item.reply}
                  </p>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>Last 5 replies</CardTitle>
          <CardDescription>
            Newest first. This list updates automatically when the worker answers
            a comment
            {liveAt ? ` · synced ${new Date(liveAt).toLocaleTimeString()}` : ""}.
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
