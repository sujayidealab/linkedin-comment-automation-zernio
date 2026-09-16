#!/usr/bin/env python3
"""Every 2 minutes, reply to new comments on all LinkedIn posts.

    python3 scripts/linkedin_comment_cron.py
    python3 scripts/linkedin_comment_cron.py --once --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from lib._env import load_env
from lib.comment_automation import run_once, snapshot, set_enabled


def main() -> int:
    load_env()
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--snapshot", action="store_true")
    ap.add_argument("--enable", action="store_true")
    ap.add_argument("--pause", action="store_true")
    ap.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("COMMENT_AUTOMATION_INTERVAL_SECONDS", "30")),
    )
    args = ap.parse_args()

    if args.pause:
        print(json.dumps(set_enabled(False)))
        return 0
    if args.enable:
        print(json.dumps(set_enabled(True)))
        return 0
    if args.snapshot:
        print(json.dumps(snapshot(), default=str))
        return 0
    if args.once:
        result = run_once(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, default=str))
        return 0 if result.get("ok") else 1

    print(
        f"LinkedIn comment cron every {args.interval}s "
        f"(account {os.getenv('ZERNIO_LINKEDIN_ACCOUNT_ID', 'auto')})",
        flush=True,
    )
    while True:
        try:
            result = run_once(dry_run=args.dry_run)
            print(
                f"[{result.get('at')}] queued={result.get('queued')} "
                f"replied={result.get('replied')} errors={len(result.get('errors') or [])}",
                flush=True,
            )
            for err in result.get("errors") or []:
                print(f"  error: {err}", flush=True)
        except Exception as exc:
            print(f"run failed: {type(exc).__name__}: {exc}", flush=True)
        time.sleep(max(args.interval, 15))


if __name__ == "__main__":
    raise SystemExit(main())
