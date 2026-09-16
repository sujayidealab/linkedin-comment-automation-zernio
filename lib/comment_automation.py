"""Reply to new LinkedIn comments on every connected post."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import fcntl
import json
import os
import random
import re
import time

from ._env import load_env
from .zernio_client import ZernioClient, ZernioError

ACTIVITY_URN = re.compile(r"urn:li:activity:\d+")
SHARE_URN = re.compile(r"urn:li:share:\d+")
COMMENT_URN = re.compile(r"urn:li:comment:\([^)]+\)")


ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "automation-state.json"
LOCK_PATH = ROOT / "data" / "automation-state.lock"
MAX_REPLIED_IDS = 20000
MAX_RUNS = 40
MAX_RECENT = 5

# Share inbox listings lag; always also fetch the matching activity URN.
DEFAULT_POST_PAIRS = [
    (
        "urn:li:share:7505699050357399554",
        "urn:li:activity:7505699050781073409",
    ),
    (
        "urn:li:share:7505696027887357954",
        "urn:li:activity:7505696030609473536",
    ),
]

TEMPLATES = [
    "{name}, thanks for jumping in. What's the piece of this that's been hardest on your side?",
    "{name}, appreciate you reading. Curious what you're running into in the workflow itself.",
    "Thanks {name}. If you had to name one bottleneck between prototype and something people trust, what is it?",
    "{name}, good to have you here. What's the setup you're working with right now?",
    "Appreciate the comment, {name}. Want to share a bit more about what you're building?",
]

DEFAULT_STATE = {
    "repliedCommentIds": [],
    "seenCommentIds": [],
    "lastRunAt": None,
    "lastError": None,
    "runs": [],
    "enabled": True,
    "recentReplies": [],
    "postAliases": {},
}


def owner_ids() -> set[str]:
    pid = os.getenv("ZERNIO_OWNER_PERSON_ID", "X5ie8NmZTi").strip() or "X5ie8NmZTi"
    return {pid, f"urn:li:person:{pid}", "X5ie8NmZTi", "urn:li:person:X5ie8NmZTi"}


def known_post_pairs() -> list[tuple[str, str]]:
    pairs = list(DEFAULT_POST_PAIRS)
    extra = os.getenv("ZERNIO_POST_PAIRS", "")
    for chunk in extra.split(","):
        chunk = chunk.strip()
        if "|" not in chunk:
            continue
        share, activity = [p.strip() for p in chunk.split("|", 1)]
        if share and activity:
            pairs.append((share, activity))
    # unique, preserve order
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for item in pairs:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_state() -> dict[str, Any]:
    state = dict(DEFAULT_STATE)
    if STATE_PATH.is_file():
        try:
            loaded = json.loads(STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                state.update(loaded)
        except json.JSONDecodeError:
            pass
    return state


def recent_replies(state: dict[str, Any]) -> list[dict[str, Any]]:
    stored = state.get("recentReplies") or []
    if stored:
        return stored[:5]
    out: list[dict[str, Any]] = []
    for run in state.get("runs") or []:
        if run.get("dryRun"):
            continue
        if not run.get("replied"):
            continue
        for sample in run.get("samples") or []:
            out.append(
                {
                    "at": run.get("at"),
                    "commenter": sample.get("commenter"),
                    "comment": sample.get("comment"),
                    "reply": sample.get("reply"),
                }
            )
            if len(out) >= 5:
                return out
    return out


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ids = list(dict.fromkeys(state.get("repliedCommentIds") or []))
    if len(ids) > MAX_REPLIED_IDS:
        ids = ids[-MAX_REPLIED_IDS:]
    state["repliedCommentIds"] = ids
    state["runs"] = list(state.get("runs") or [])[:MAX_RUNS]
    state["recentReplies"] = list(state.get("recentReplies") or [])[:MAX_RECENT]
    tmp = STATE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
    tmp.replace(STATE_PATH)


def _state_lock():
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOCK_PATH, "a+", encoding="utf-8")
    fcntl.flock(handle, fcntl.LOCK_EX)
    return handle


def seed_aliases(aliases: dict[str, list[str]]) -> dict[str, list[str]]:
    for share, activity in known_post_pairs():
        learned = sorted({share, activity, *(aliases.get(share) or []), *(aliases.get(activity) or [])})
        aliases[share] = learned
        aliases[activity] = learned
    return aliases


def _person_id(from_: dict[str, Any]) -> str:
    return str(from_.get("id") or "")


def _is_owner(from_: dict[str, Any]) -> bool:
    pid = _person_id(from_)
    owners = owner_ids()
    if pid in owners:
        return True
    if any(pid.endswith(oid) for oid in owners if not oid.startswith("urn:")):
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


def _urns_in(text: str) -> set[str]:
    return set(ACTIVITY_URN.findall(text or "")) | set(SHARE_URN.findall(text or ""))


def activity_urn_from_comment_id(comment_id: str) -> str | None:
    found = ACTIVITY_URN.findall(comment_id or "")
    return found[0] if found else None


def _lookup_ids(post_id: str, aliases: dict[str, list[str]], comments: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for value in [post_id, *aliases.get(post_id, [])]:
        if value and value not in ids:
            ids.append(value)
    blob = " ".join(str(c.get("id") or "") for c in comments)
    for urn in _urns_in(blob):
        if urn not in ids:
            ids.append(urn)
    return ids


def load_comments_for_post(
    client: ZernioClient, post_id: str, aliases: dict[str, list[str]]
) -> tuple[list[dict[str, Any]], str]:
    """LinkedIn share URNs can lag; activity URNs have the live thread."""
    merged: dict[str, dict[str, Any]] = {}
    ids = _lookup_ids(post_id, aliases, [])
    for ident in ids:
        for comment in client.get_inbox_comments_raw(ident, max_items=100):
            _put_comment(merged, comment)
    extra = _lookup_ids(post_id, aliases, list(merged.values()))
    for ident in extra:
        if ident in ids:
            continue
        for comment in client.get_inbox_comments_raw(ident, max_items=100):
            _put_comment(merged, comment)
        ids.append(ident)
    reply_post_id = next((i for i in ids if i.startswith("urn:li:activity:")), post_id)
    return list(merged.values()), reply_post_id


def _comment_reply_score(comment: dict[str, Any]) -> int:
    replies = comment.get("replies") or []
    return max(len(replies), int(comment.get("replyCount") or 0))


def _put_comment(merged: dict[str, dict[str, Any]], comment: dict[str, Any]) -> None:
    cid = str(comment.get("id") or "")
    if not cid:
        return
    existing = merged.get(cid)
    if existing is None or _comment_reply_score(comment) >= _comment_reply_score(existing):
        merged[cid] = comment


def collect_targets(client: ZernioClient, state: dict[str, Any]) -> list[dict[str, Any]]:
    replied = set(state.get("repliedCommentIds") or [])
    aliases: dict[str, list[str]] = seed_aliases(state.setdefault("postAliases", {}))
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
    for share, activity in known_post_pairs():
        for pid in (activity, share):
            if pid not in seen_ids:
                seen_ids.add(pid)
                feed.append({"id": pid, "content": "", "permalink": None, "commentCount": 0})

    fetched: set[str] = set()
    seen_targets: set[str] = set()
    for post in feed:
        post_id = str(post.get("id") or "")
        if not post_id or post_id in fetched:
            continue
        lookup = _lookup_ids(post_id, aliases, [])
        if fetched.intersection(lookup):
            fetched.update(lookup)
            continue
        comments, reply_post_id = load_comments_for_post(client, post_id, aliases)
        learned = sorted(
            {
                post_id,
                reply_post_id,
                *lookup,
                *(_urns_in(" ".join(str(c.get("id") or "") for c in comments))),
            }
        )
        fetched.update(learned)
        for urn in learned:
            aliases[urn] = learned
        for comment in comments:
            cid = str(comment.get("id") or "")
            if not cid or cid in replied or cid in seen_targets:
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
            seen_targets.add(cid)
            targets.append(
                {
                    "postId": activity_urn_from_comment_id(cid) or reply_post_id,
                    "postPreview": (post.get("content") or "")[:160],
                    "permalink": post.get("permalink"),
                    "commentId": cid,
                    "commentText": text,
                    "commenter": from_.get("name") or from_.get("username") or "someone",
                    "reply": _compose_reply(from_),
                }
            )
    state["repliedCommentIds"] = sorted(replied)
    state["postAliases"] = aliases
    return targets


def run_once(*, dry_run: bool = False, max_replies: int = 20) -> dict[str, Any]:
    load_env()
    lock = _state_lock()
    try:
        return _run_once_locked(dry_run=dry_run, max_replies=max_replies)
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def _run_once_locked(*, dry_run: bool = False, max_replies: int = 20) -> dict[str, Any]:
    load_env()
    state = load_state()
    if "enabled" not in state:
        state["enabled"] = os.getenv("COMMENT_AUTOMATION_ENABLED", "true").lower() not in {
            "0",
            "false",
            "no",
        }
    enabled = bool(state.get("enabled", True))
    if not enabled:
        result = {
            "ok": True,
            "skipped": True,
            "reason": "automation paused from the dashboard",
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
                time.sleep(float(os.getenv("COMMENT_REPLY_DELAY_SECONDS", "2.5")))
            except ZernioError as exc:
                errors.append(f"{item['commentId']}: {exc}")
    else:
        sent = []

    if sent:
        new_rows = [
            {
                "at": _now(),
                "commenter": t["commenter"],
                "comment": t["commentText"][:280],
                "reply": t["reply"],
                "permalink": t.get("permalink"),
                "commentId": t["commentId"],
            }
            for t in sent
        ]
        state["recentReplies"] = (new_rows + list(state.get("recentReplies") or []))[:5]
    elif not state.get("recentReplies"):
        state["recentReplies"] = recent_replies(state)

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
    state["runs"] = ([run_row] + state["runs"])[:MAX_RUNS]
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


def set_enabled(enabled: bool) -> dict[str, Any]:
    lock = _state_lock()
    try:
        state = load_state()
        state["enabled"] = bool(enabled)
        save_state(state)
        return {"enabled": state["enabled"]}
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


def snapshot() -> dict[str, Any]:
    load_env()
    state = load_state()
    client = ZernioClient()
    accounts = [
        a
        for a in client.list_accounts()
        if str(a.get("platform", "")).lower() == "linkedin"
    ]
    account = accounts[0] if accounts else {}
    posts = client.list_inbox_posts(platform="linkedin", limit=50)
    targets = collect_targets(client, state)
    save_state(state)
    unanswered_ids = {t["commentId"] for t in targets}
    post_rows = []
    for post in posts:
        post_rows.append(
            {
                "id": post.get("id"),
                "preview": (post.get("content") or "").strip(),
                "permalink": post.get("permalink"),
                "commentCount": post.get("commentCount") or 0,
                "createdTime": post.get("createdTime"),
            }
        )
    return {
        "ok": True,
        "enabled": bool(state.get("enabled", True)),
        "lastRunAt": state.get("lastRunAt"),
        "handled": len(state.get("repliedCommentIds") or []),
        "account": {
            "id": account.get("_id"),
            "name": account.get("displayName") or account.get("username"),
            "username": account.get("username"),
            "profileUrl": account.get("profileUrl"),
            "picture": account.get("profilePicture"),
            "followers": account.get("followersCount"),
        },
        "posts": post_rows,
        "unanswered": targets,
        "unansweredCount": len(unanswered_ids),
        "recentReplies": recent_replies(state),
        "intervalSeconds": int(os.getenv("COMMENT_AUTOMATION_INTERVAL_SECONDS", "30")),
    }
