#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8080}"
export PYTHONUNBUFFERED=1

if [[ -z "${ZERNIO_API_KEY:-}" && ! -f .env ]]; then
  echo "ZERNIO_API_KEY is not set. Add it as a Railway variable or put it in .env" >&2
  exit 1
fi

if [[ ! -d .next ]]; then
  echo "No production build. Run: npm run build" >&2
  exit 1
fi

mkdir -p data

worker() {
  while true; do
    python3 scripts/linkedin_comment_cron.py || true
    echo "Comment worker exited; restarting in 5s" >&2
    sleep 5
  done
}

worker &
CRON_PID=$!
cleanup() {
  kill "$CRON_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "Comment worker supervisor pid $CRON_PID"
echo "App 0.0.0.0:${PORT}"
exec npx next start --hostname 0.0.0.0 --port "$PORT"
