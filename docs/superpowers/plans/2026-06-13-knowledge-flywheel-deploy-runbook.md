# Knowledge Flywheel (B) — Deploy Runbook & State

Records what was deployed/wired in prod for subsystem B, so it's reproducible.
**Secrets (the Notion integration token) are NOT in this file** — they live Fernet-encrypted in PG (`notion_tokens`) and in nothing else.

## Notion structure (created via the claude.ai Notion MCP)
Parent page **「VI 知识库 · Knowledge Base」** with 3 databases (schema matches `capture.py` property names exactly; two-way relations 笔记↔概念 / 笔记↔来源):

| DB | database_id (env var) |
|---|---|
| 笔记 Notes | `VI_NOTION_DB_NOTES=47e94574289249599821e4f7ad104776` |
| 概念 Concepts | `VI_NOTION_DB_CONCEPTS=f6e8523ad6de48f58141284ec74d22dd` |
| 信息源 Sources | `VI_NOTION_DB_SOURCES=7331c19c666c4ffda86bef9e7f6cc226` |

A Notion **internal integration** ("VI Backend") was created by the user; the parent page is shared with it (→ all 3 child DBs inherit access). Its token is stored via `set_notion_token("lucas", …)` (Fernet, key derived from `VI_SECRET_KEY`).

## Backend deploy (`/opt/value-investment-api/`, gunicorn `value-investment-api.service`, venv = Python 3.13)
1. `pip install notion-client>=2.2 mcp` into the API venv.
2. Copied: `app.py capture.py notion_kb.py mcp_server.py mcp_server_launch.sh requirements.txt requirements-mcp.txt`, `skills/vi-capture-note/SKILL.md`.
3. Appended `VI_NOTION_DB_*` to `/etc/value-investment/api.env`; `systemctl restart value-investment-api` (→ `_init_db` created `captures`/`kb_concepts`/`kb_sources`/`notion_tokens`).
4. `POST /api/notion/token {token}` (or `set_notion_token`) to store the token.

**Verified in prod:** `do_capture("lucas", …)` → PG `captures` row + real Notion Note + Concept pages + receipt. ✅

## hermes wiring (app-lucas profile)
- `hermes -p app-lucas mcp add vi-capture --command /opt/value-investment-api/mcp_server_launch.sh` (3 tools: `capture_note` / `list_concepts` / `list_sources`).
- `seed.py` (SKILL.md → `official_skills`) + `provision_hermes()` (→ each `app-*` profile's `skills/`).
- Appended a `## 知识沉淀` block to `~/.hermes/profiles/app-lucas/SOUL.md` (when to capture; `user`→`lucas`; distill qualitative memory).
- `hermes -p app-lucas tools enable memory` (native MEMORY.md/USER.md = mechanism B).

**Verified end-to-end:** `hermes -p app-lucas -z "<a worth-keeping thought>"` → hermes autonomously called `capture_note` → Notion Note created + receipt. ✅
(Note: `hermes -z` drops the foreground SSH session when it restarts its gateway — run detached: `setsid bash -c "… > /tmp/out 2>&1" </dev/null >/dev/null 2>&1 &`, then read the file.)

## ⚠️ Open: the Feishu channel
The Feishu bot runs as a **system service (`hermes-gateway.service`) under the `default` profile**, which has NO vi-capture MCP/skill/SOUL. Capture is wired on the **per-user `app-*`** profiles (used by the web app's `run_skill`). So:
- **Web-app path** (chat / future quick-capture via `run_skill(user, …)` on `app-<user>`): capture capability is present.
- **Feishu path**: needs a routing decision — how an inbound Feishu message from lucas reaches `app-lucas`'s capture (the `default` bot doesn't know the sender→user mapping). This is the spec's flagged "飞书入站待实测" item. Options to evaluate: (a) add vi-capture to `default` + sender→user mapping; (b) a per-user gateway (app-lucas already has a manual gateway running); (c) route Feishu inbound → backend `/api/capture` → run on `app-<user>`.

## Remaining
- Decide + wire the Feishu channel (above).
- Wire `app-aris` / `app-shihan` the same way (per-profile SOUL `user`) when they connect Notion.
- Mechanism B verification (native memory accumulates "who lucas is" across sessions).
- Optional: a `/api/captures/retry` endpoint or cron (currently retry drains opportunistically after each successful capture).
