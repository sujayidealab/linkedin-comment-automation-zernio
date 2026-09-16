# LinkedIn comment automation (Zernio)

Watches **every LinkedIn post** on the connected Zernio account and auto-replies to new top-level comments. A worker runs every **30 seconds**.

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # set ZERNIO_API_KEY
python3 scripts/linkedin_comment_cron.py --once --dry-run
python3 scripts/linkedin_comment_cron.py          # live loop, 30s
npm install
npm run dev -- --hostname 0.0.0.0 --port 43147
```

The worker checks every 30 seconds, fetches both share and activity URNs, and skips threads it already answered. State is file-locked and capped so it can run 24/7 on Railway without unbounded growth. Extra posts: `ZERNIO_POST_PAIRS=share|activity,share|activity`.

Copy `.env.example` to `.env` and put your Zernio key in it. Do not commit `.env` — GitHub would expose the key. On Railway, set the same names as Variables.

## Railway (24/7)

This repo is set up to run on Railway: `Dockerfile` + `railway.json` start both the dashboard and the comment worker. Railway must provide `ZERNIO_API_KEY` (and optionally `ZERNIO_LINKEDIN_ACCOUNT_ID`, `ZERNIO_OWNER_PERSON_ID`). Generate a public domain on the service after deploy.

# LinkedIn skills + Zernio MCP


A Cursor-ready fork of [sergebulaev/linkedin-skills](https://github.com/sergebulaev/linkedin-skills): 11 LinkedIn content skills (draft → approve → publish) wired to **Zernio** instead of Publora and Apify.

- REST: `https://zernio.com/api/v1` with `Authorization: Bearer $ZERNIO_API_KEY`
- Hosted MCP: `https://mcp.zernio.com/mcp` (same key)
- Docs: https://docs.zernio.com · signup: https://zernio.com/signup

## Setup

1. Copy `.env.example` to `.env` and add your Zernio API key from [API keys](https://zernio.com/dashboard/api-keys).
2. Connect a LinkedIn account in the [Zernio dashboard](https://zernio.com/dashboard).
3. Install Python deps:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/check_config.py --offline
```

4. Cursor MCP is already described in `.cursor/mcp.json`. Add your key as a Cursor secret named `ZERNIO_API_KEY`, or paste it into the MCP Authorization header locally. Do not commit the key.

Cursor MCP shape:

```json
{
  "mcpServers": {
    "zernio": {
      "url": "https://mcp.zernio.com/mcp",
      "headers": {
        "Authorization": "Bearer ${ZERNIO_API_KEY}"
      }
    }
  }
}
```

Autonomous agents can call MCP with the same Bearer header ([Zernio MCP docs](https://docs.zernio.com/resources/mcp)).

## Skills

| Skill | Use |
|---|---|
| `linkedin-post-writer` | Draft a new post |
| `linkedin-comment-drafter` | Comment or reshare from a post URL |
| `linkedin-reply-handler` | Reply / sweep a thread |
| `linkedin-humanizer` | Strip AI tells, audit before publish |
| `linkedin-hook-extractor` | Pull hook formulas from a post |
| `linkedin-content-planner` | Week plan |
| `linkedin-thread-monitor` | Follow-up on your comments |
| `linkedin-engager-analytics` | Who commented (connected posts) |
| `linkedin-profile-optimizer` | Profile rewrite |
| `linkedin-employee-advocacy` | Team advocacy |
| `linkedin-repurposer` | Other-platform → LinkedIn |
| `linkedin-interviewer` | Story bank |

Agents should load `SKILL.md` and the matching file under `skills/*/SKILL.md`.

## What Zernio replaces

| Original | This fork |
|---|---|
| Publora publish / comments / reactions | `ZernioClient` → `/v1/posts`, `/v1/inbox/comments`, likes |
| Apify public scrapers | Connected-account inbox + analytics; paste text for public posts Zernio cannot see |
| Publora MCP | Zernio MCP at `https://mcp.zernio.com/mcp` |

Pixfaro remains optional for illustrations (`PIXFARO_TOKEN`).

## License

Original LinkedIn skills: MIT (Sergey Bulaev). This workspace is a Zernio-backed adaptation of that bundle.
