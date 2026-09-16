"""Reply to new LinkedIn comments on every connected post."""
from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._env import load_env
from .zernio_client import ZernioClient, ZernioError

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "automation-state.json"

TEMPLATES = [
    "{name}, thanks for jumping in. What's the piece of this that's been hardest on your side?",
    "{name}, appreciate you reading. Curious what you're running into in the workflow itself.",
    "Thanks {name}. If you had to name one bottleneck between prototype and something people trust, what is it?",
    "{name}, good to have you here. What's the setup you're working with right now?",
    "Appreciate the comment, {name}. Want to share a bit more about what you're building?",
]

OWNER_IDS = {
    os.getenv("ZERNIO_OWNER_PERSON_ID", "X5ie8NmZTi"),
    "urn:li:person:X5ie8NmZTi",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict[str, Any]:
    if STATE_PATH.is_file():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "repliedCommentIds": [],
        "seenCommentIds": [],
        "lastRunAt": None,
        "lastError": None,
        "runs": [],
        "enabled": True,
    }


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _person_id(from_: dict[str, Any]) -> str:
    return str(from_.get("id") or "")


def _is_owner(from_: dict[str, Any]) -> bool:
    pid = _person_id(from_)
    if pid in OWNER_IDS:
        return True
    if pid.endswith("X5ie8NmZTi"):
        return True
    name = (from_.get("name") or "").lower()
    return name == "sujay viston"


def _first_name(from_: dict[str, Any]) -> str:
    name = (from_.get("name") or "there").strip()
    return name.split()[0] if name else "there"


def _owner_already_replied(comment: dict[str, Any]) -> bool:
    for reply in comment.get("replies") or []:
        if _is_owner(reply.get("from") or {}):
            return True
    return False


def _compose_reply(from_: dict[str, Any]) -> str:
    template = random.choice(TEMPLATES)
    return template.format(name=_first_name(from_))


def collect_targets(client: ZernioClient, state: dict[str, Any]) -> list[dict[str, Any]]:
    replied = set(state.get("repliedCommentIds") or [])
    targets: list[dict[str, Any]] = []
    posts = client.list_inbox_posts(platform="linkedin", limit=50)
    published = client.list_posts(platform="linkedin", limit=50)
    seen_ids: set[str] = set()
    feed: list[dict[str, Any]] = []
    for p in posts:
        pid = str(p.get("id") or "")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            feed.append(p)
    for p in published:
        platforms = p.get("platforms") or []
        for row in platforms:
            pid = str(row.get("platformPostId") or "")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                feed.append(
                    {
                        "id": pid,
                        "content": p.get("content") or "",
                        "permalink": row.get("platformPostUrl"),
                        "commentCount": 0,
                    }
                )

    for post in feed:
        post_id = str(post.get("id") or "")
        if not post_id:
            continue
        comments = client.get_inbox_comments_raw(post_id, max_items=100)
        for comment in comments:
            cid = str(comment.get("id") or "")
            if not cid or cid in replied:
                continue
            from_ = comment.get("from") or {}
            if _is_owner(from_):
                continue
            if _owner_already_replied(comment):
                replied.add(cid)
                continue
            text = (comment.get("message") or comment.get("text") or "").strip()
            if not text:
                continue
            targets.append(
                {
                    "postId": post_id,
                    "postPreview": (post.get("content") or "")[:160],
                    "permalink": post.get("permalink"),
                    "commentId": cid,
                    "commentText": text,
                    "commenter": from_.get("name") or from_.get("username") or "someone",
                    "reply": _compose_reply(from_),
                }
            )
    state["repliedCommentIds"] = sorted(replied)
    return targets


def run_once(*, dry_run: bool = False, max_replies: int = 20) -> dict[str, Any]:
    load_env()
    enabled = os.getenv("COMMENT_AUTOMATION_ENABLED", "true").lower() not in {
        "0",
        "false",
        "no",
    }
    state = load_state()
    if os.getenv("COMMENT_AUTOMATION_ENABLED") is None:
        enabled = bool(state.get("enabled", True))
    if not enabled:
        result = {
            "ok": True,
            "skipped": True,
            "reason": "automation disabled",
            "replied": 0,
            "queued": 0,
            "at": _now(),
        }
        state["lastRunAt"] = _now()
        save_state(state)
        return result

    client = ZernioClient()
    targets = collect_targets(client, state)
    sent: list[dict[str, Any]] = []
    errors: list[str] = []
    if not dry_run:
        for item in targets[:max_replies]:
            try:
                client.create_comment(
                    post_urn=item["postId"],
                    message=item["reply"],
                    parent_comment=item["commentId"],
                )
                state.setdefault("repliedCommentIds", []).append(item["commentId"])
                sent.append(item)
                time.sleep(2.5)
            except ZernioError as exc:
                errors.append(f"{item['commentId']}: {exc}")
    else:
        sent = []

    state["repliedCommentIds"] = sorted(set(state.get("repliedCommentIds") or []))
    state["lastRunAt"] = _now()
    state["lastError"] = errors[-1] if errors else None
    run_row = {
        "at": _now(),
        "dryRun": dry_run,
        "queued": len(targets),
        "replied": 0 if dry_run else len(sent),
        "errors": errors,
        "samples": [
            {
                "commenter": t["commenter"],
                "comment": t["commentText"][:180],
                "reply": t["reply"],
            }
            for t in (targets if dry_run else sent)[:8]
        ],
    }
    state.setdefault("runs", [])
    state["runs"] = ([run_row] + state["runs"])[:25]
    save_state(state)
    return {
        "ok": not errors,
        "dryRun": dry_run,
        "queued": len(targets),
        "replied": 0 if dry_run else len(sent),
        "errors": errors,
        "targets": targets[:20],
        "at": _now(),
    }
