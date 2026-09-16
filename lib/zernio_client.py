"""Thin Zernio REST client for LinkedIn Skills.

Publishing, comments, analytics, and connected-account reads go through
https://zernio.com/api/v1 with Authorization: Bearer $ZERNIO_API_KEY.

Zernio is not a public LinkedIn scraper. Reads work on accounts you connected
in the Zernio dashboard, plus LinkedIn third-party posts when the inbox
comment APIs accept an activity URN. When a fetch is not possible, skills
fall back to asking you to paste the post text.
"""
from __future__ import annotations

import os
import random
import time
from typing import Any, Optional
from urllib.parse import quote

import requests

from ._env import load_env


class ZernioError(RuntimeError):
    pass


RETRYABLE_STATUSES = {408, 429, 500, 502, 503, 504}


def _retry(attempts: int = 3, base_delay: float = 0.6):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last_exc: Optional[Exception] = None
            for attempt in range(attempts):
                try:
                    return fn(*args, **kwargs)
                except ZernioError as e:
                    retryable = any(f"HTTP {s}" in str(e) for s in RETRYABLE_STATUSES)
                    if not retryable or attempt == attempts - 1:
                        raise
                    last_exc = e
                except (requests.ConnectionError, requests.Timeout) as e:
                    if attempt == attempts - 1:
                        raise
                    last_exc = e
                time.sleep(base_delay * (2**attempt) + random.uniform(0, 0.25))
            assert last_exc is not None
            raise last_exc

        return wrapper

    return decorator


class ZernioClient:
    BASE_URL = "https://zernio.com/api/v1"
    MCP_URL = "https://mcp.zernio.com/mcp"

    LIVE_STATUSES = ("published", "partial", "publishing")

    def __init__(self, api_key: Optional[str] = None, timeout: float = 30.0):
        load_env()
        self.api_key = api_key or os.getenv("ZERNIO_API_KEY")
        if not self.api_key:
            raise ZernioError(
                "ZERNIO_API_KEY not set. Create a key at https://zernio.com/dashboard/api-keys"
            )
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            }
        )

    def list_accounts(self, profile_id: Optional[str] = None) -> list[dict[str, Any]]:
        params = {}
        if profile_id:
            params["profileId"] = profile_id
        r = self._session.get(f"{self.BASE_URL}/accounts", params=params, timeout=self.timeout)
        payload = self._handle(r)
        rows = payload.get("accounts") or payload.get("data") or payload
        return rows if isinstance(rows, list) else []

    def resolve_linkedin_account_id(self) -> Optional[str]:
        env_id = os.getenv("ZERNIO_LINKEDIN_ACCOUNT_ID") or os.getenv("LINKEDIN_ACCOUNT_ID")
        if env_id:
            return env_id
        linkedin = [
            a.get("_id") or a.get("id")
            for a in self.list_accounts()
            if str(a.get("platform", "")).lower() == "linkedin" and a.get("isActive", True)
        ]
        linkedin = [i for i in linkedin if i]
        return linkedin[0] if len(linkedin) == 1 else None

    def create_comment(
        self,
        *,
        post_urn: str,
        message: str,
        platform_id: Optional[str] = None,
        parent_comment: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        if len(message) > 1250:
            raise ZernioError("message exceeds 1,250 char LinkedIn limit")
        account_id = account_id or platform_id or self.resolve_linkedin_account_id()
        if not account_id:
            raise ZernioError(
                "No LinkedIn account id. Connect LinkedIn in Zernio or set ZERNIO_LINKEDIN_ACCOUNT_ID."
            )
        post_id = quote(_linkedin_post_id(post_urn), safe="")
        body: dict[str, Any] = {"accountId": account_id, "message": message}
        if parent_comment:
            body["commentId"] = _linkedin_comment_id(parent_comment)
        return self._post(f"/inbox/comments/{post_id}", body)

    def delete_comment(
        self,
        *,
        post_urn: str,
        comment_id: str,
        platform_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        account_id = account_id or platform_id or self.resolve_linkedin_account_id()
        post_id = quote(_linkedin_post_id(post_urn), safe="")
        r = self._session.delete(
            f"{self.BASE_URL}/inbox/comments/{post_id}",
            params={"accountId": account_id, "commentId": comment_id},
            timeout=self.timeout,
        )
        return self._handle(r)

    def create_reaction(
        self,
        *,
        post_urn: str,
        platform_id: Optional[str] = None,
        reaction_type: str = "LIKE",
        account_id: Optional[str] = None,
    ) -> dict[str, Any]:
        account_id = account_id or platform_id or self.resolve_linkedin_account_id()
        post_id = _linkedin_post_id(post_urn)
        return self._post(
            f"/inbox/posts/{post_id}/like",
            {"accountId": account_id, "reaction": reaction_type.lower()},
        )

    def create_post(
        self,
        *,
        content: str,
        platforms: Optional[list] = None,
        scheduled_time: Optional[str] = None,
        media_urls: Optional[list[str]] = None,
        publish_now: bool = False,
    ) -> dict[str, Any]:
        account_id = self.resolve_linkedin_account_id()
        platform_entries = []
        if platforms:
            for p in platforms:
                if isinstance(p, str) and p.startswith("linkedin"):
                    platform_entries.append(
                        {"platform": "linkedin", "accountId": account_id or p}
                    )
                elif isinstance(p, dict):
                    platform_entries.append(
                        {
                            "platform": p.get("platform") or "linkedin",
                            "accountId": p.get("accountId")
                            or p.get("platformId")
                            or account_id,
                        }
                    )
                elif p:
                    platform_entries.append({"platform": "linkedin", "accountId": p})
        if not platform_entries:
            if not account_id:
                raise ZernioError(
                    "No LinkedIn account connected. Set ZERNIO_LINKEDIN_ACCOUNT_ID or connect LinkedIn at https://zernio.com/dashboard"
                )
            platform_entries = [{"platform": "linkedin", "accountId": account_id}]

        payload: dict[str, Any] = {"content": content, "platforms": platform_entries}
        if scheduled_time:
            payload["scheduledFor"] = scheduled_time
        elif publish_now:
            payload["publishNow"] = True
        else:
            payload["isDraft"] = True
        if media_urls:
            payload["mediaItems"] = [{"type": "image", "url": u} for u in media_urls]
        return self._post("/posts", payload)

    def get_post(self, *, post_group_id: str) -> dict[str, Any]:
        r = self._session.get(f"{self.BASE_URL}/posts/{post_group_id}", timeout=self.timeout)
        return self._handle(r)

    def delete_post(self, *, post_group_id: str, allow_live: bool = False) -> dict[str, Any]:
        if not allow_live:
            try:
                group = self.get_post(post_group_id=post_group_id)
            except ZernioError:
                group = {}
            status = (group.get("post") or group).get("status")
            if status in self.LIVE_STATUSES:
                raise ZernioError(
                    f"refusing to delete post {post_group_id}: status is {status!r}. "
                    "Delete it on LinkedIn instead, or pass allow_live=True."
                )
        r = self._session.delete(f"{self.BASE_URL}/posts/{post_group_id}", timeout=self.timeout)
        return self._handle(r)

    def create_reshare(
        self,
        *,
        parent: str,
        platform_id: Optional[str] = None,
        commentary: Optional[str] = None,
        visibility: str = "PUBLIC",
    ) -> dict[str, Any]:
        """Reshare as a new LinkedIn post whose body is the commentary.

        Zernio's posts API publishes original content; it does not wrap a
        LinkedIn share URN the way Publora did. Use commentary as the post body.
        """
        if not commentary:
            raise ZernioError(
                "Zernio publishes a new post rather than a native LinkedIn reshare. "
                "Pass commentary text to post, or reshare by hand in LinkedIn."
            )
        return self.create_post(
            content=commentary,
            platforms=[{"platform": "linkedin", "accountId": platform_id}] if platform_id else None,
            publish_now=True,
        )

    def list_posts(self, *, platform: str = "linkedin", limit: int = 25) -> list[dict[str, Any]]:
        r = self._session.get(
            f"{self.BASE_URL}/posts",
            params={"platform": platform, "limit": limit},
            timeout=self.timeout,
        )
        payload = self._handle(r)
        rows = payload.get("posts") or payload.get("data") or []
        return rows if isinstance(rows, list) else []

    def list_inbox_posts(self, *, platform: str = "linkedin", limit: int = 50) -> list[dict[str, Any]]:
        account_id = self.resolve_linkedin_account_id()
        params: dict[str, Any] = {
            "platform": platform,
            "limit": min(limit, 100),
            "_ts": int(time.time() * 1000),
        }
        if account_id:
            params["accountId"] = account_id
        r = self._session.get(
            f"{self.BASE_URL}/inbox/comments",
            params=params,
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=self.timeout,
        )
        payload = self._handle(r)
        rows = payload.get("data") or payload.get("posts") or []
        return rows if isinstance(rows, list) else []

    def get_inbox_comments_raw(
        self, post_id: str, *, max_items: int = 100
    ) -> list[dict[str, Any]]:
        account_id = self.resolve_linkedin_account_id()
        if not account_id:
            return []
        pid = quote(_linkedin_post_id(post_id), safe="")
        r = self._session.get(
            f"{self.BASE_URL}/inbox/comments/{pid}",
            params={
                "accountId": account_id,
                "limit": min(max_items, 100),
                "_ts": int(time.time() * 1000),
            },
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=self.timeout,
        )
        payload = self._handle(r)
        comments = payload.get("comments") or payload.get("data") or []
        return comments if isinstance(comments, list) else []

    def fetch_post(self, post_url: str, *, force_refresh: bool = False) -> dict[str, Any]:
        """Best-effort post body from connected LinkedIn data or inbox comments."""
        del force_refresh
        account_id = self.resolve_linkedin_account_id()
        post_id = _linkedin_post_id(post_url)

        for post in self.list_posts(limit=50):
            blob = json_dumps_safe(post)
            if post_id and post_id in blob:
                text = post.get("content") or ""
                return {
                    "text": text,
                    "authorName": "",
                    "authorProfileUrl": "",
                    "urn": post_id,
                    "shareUrn": "",
                    "canShare": True,
                    "url": post_url,
                    "numLikes": 0,
                    "numComments": 0,
                    "numShares": 0,
                    "postedAtISO": post.get("scheduledFor") or post.get("createdAt"),
                    "zernioPostId": post.get("_id"),
                }

        if account_id and post_id:
            comments = self.fetch_post_comments(post_id=post_id, max_items=5)
            if comments:
                return {
                    "text": "",
                    "authorName": "",
                    "authorProfileUrl": "",
                    "urn": post_id,
                    "shareUrn": post_id if str(post_id).startswith("urn:li:") else "",
                    "canShare": True,
                    "url": post_url,
                    "numLikes": 0,
                    "numComments": len(comments),
                    "numShares": 0,
                    "commentsPreview": comments,
                }
        raise ZernioError(
            "Could not load that LinkedIn post via Zernio. Paste the post text, "
            "or connect the LinkedIn account that owns it."
        )

    def fetch_post_comments(
        self, post_id: str, *, max_items: int = 50, sort_order: Optional[str] = None
    ) -> list[dict[str, Any]]:
        del sort_order
        account_id = self.resolve_linkedin_account_id()
        if not account_id:
            return []
        pid = quote(_linkedin_post_id(post_id), safe="")
        r = self._session.get(
            f"{self.BASE_URL}/inbox/comments/{pid}",
            params={
                "accountId": account_id,
                "limit": min(max_items, 100),
                "_ts": int(time.time() * 1000),
            },
            headers={"Cache-Control": "no-cache", "Pragma": "no-cache"},
            timeout=self.timeout,
        )
        payload = self._handle(r)
        comments = payload.get("comments") or payload.get("data") or []
        out = []
        for c in comments[:max_items]:
            from_ = c.get("from") or {}
            out.append(
                {
                    "id": c.get("id"),
                    "text": c.get("message") or c.get("text") or "",
                    "authorName": from_.get("name") or from_.get("username") or "",
                    "comment_id": c.get("id"),
                    "parentId": c.get("parentId"),
                    "url": c.get("url"),
                    "replies": c.get("replies") or [],
                }
            )
        return out

    def fetch_user_recent_comments(
        self, username: str = "", *, result_limit: int = 30
    ) -> list[dict[str, Any]]:
        del username
        account_id = self.resolve_linkedin_account_id()
        params: dict[str, Any] = {"platform": "linkedin", "limit": min(result_limit, 100)}
        if account_id:
            params["accountId"] = account_id
        r = self._session.get(
            f"{self.BASE_URL}/inbox/comments", params=params, timeout=self.timeout
        )
        payload = self._handle(r)
        rows = payload.get("data") or payload.get("posts") or []
        out = []
        for row in rows[:result_limit]:
            out.append(
                {
                    "text": row.get("content") or "",
                    "postUrl": row.get("permalink") or "",
                    "postAuthor": row.get("accountUsername") or "",
                    "commentCount": row.get("commentCount"),
                    "id": row.get("id"),
                }
            )
        return out

    def fetch_post_engagers(
        self, post_url: str, *, max_items: int = 50, types: Optional[tuple] = None
    ) -> list[dict[str, Any]]:
        del types
        comments = self.fetch_post_comments(post_id=post_url, max_items=max_items)
        return [
            {
                "type": "commenters",
                "name": c.get("authorName") or "",
                "subtitle": "",
                "url_profile": "",
                "content": c.get("text") or "",
                "datetime": "",
            }
            for c in comments
        ]

    def post_analytics(self, post_id: str) -> dict[str, Any]:
        r = self._session.get(
            f"{self.BASE_URL}/analytics/post/{post_id}", timeout=self.timeout
        )
        return self._handle(r)

    def account_analytics(self, account_id: str, range_: str = "30d") -> dict[str, Any]:
        r = self._session.get(
            f"{self.BASE_URL}/analytics/social/{account_id}",
            params={"range": range_},
            timeout=self.timeout,
        )
        return self._handle(r)

    @_retry()
    def _post(self, path: str, json_body: dict[str, Any]) -> dict[str, Any]:
        r = self._session.post(
            self.BASE_URL + path, json=json_body, timeout=self.timeout
        )
        return self._handle(r)

    @staticmethod
    def _handle(r: requests.Response) -> dict[str, Any]:
        if r.status_code >= 400:
            try:
                body = r.json()
            except Exception:
                body = {"error": r.text[:500]}
            raise ZernioError(f"HTTP {r.status_code}: {body}")
        if not r.content:
            return {}
        try:
            return r.json()
        except Exception:
            return {"raw": r.text[:500]}


def _linkedin_post_id(value: str) -> str:
    text = (value or "").strip()
    if "activity-" in text:
        # https://www.linkedin.com/posts/name-activity-123456
        part = text.rsplit("activity-", 1)[-1].split("?")[0].split("/")[0]
        digits = "".join(ch for ch in part if ch.isdigit())
        if digits:
            return f"urn:li:activity:{digits}"
    if "urn:li:" in text:
        return text
    return text


def _linkedin_comment_id(value: str) -> str:
    return (value or "").strip()


def json_dumps_safe(obj: Any) -> str:
    try:
        import json

        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)
