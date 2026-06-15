# Content Signal Pipeline (子系统 A 第一实现)

Daily: detect new 小宇宙 episodes → Feishu notice (A) → transcribe + distill free
episodes into a 信号卡 (B). Source-agnostic behind `adapters/SourceAdapter`.

**Tracked podcasts** live in `podcasts.py` (`TRACKED_PODCASTS`). Currently:
非共识的20分钟 · 张小珺Jùn｜商业访谈录 · The Wanderers 流浪者. The per-episode show
name + cover art are auto-discovered off each page, so the daily poll and the website
already label cards per-column with no extra config.

## Run
```
# one cycle (server: needs hermes + PostgreSQL + faster-whisper)
python -m content_pipeline.run
# dry run (mock whisper+hermes, in-memory store, prints actions)
python -m content_pipeline.run --dry-run
```

## Schedule
08:00 北京时间 daily. See `run.sh` header (system cron `0 0 * * *` if server is UTC,
or `0 8 * * *` with `TZ=Asia/Shanghai`; or `hermes cron`).

## Env vars
| var | default | meaning |
|---|---|---|
| `VI_DATABASE_URL` | — | PostgreSQL DSN (same as the app) |
| `VI_PIPELINE_PODCAST_IDS` | (tracked defaults) | comma-separated 小宇宙 pids to poll (overrides the `podcasts.py` defaults) |
| `VI_PIPELINE_PODCAST_ID` | — | legacy singular; still honoured if `…_IDS` unset |
| `VI_WHISPER_MODE` | `whisper` | `mock` to skip the model |
| `VI_PIPELINE_PROFILE` | `app-lucas` | hermes profile for the distill skill |
| `VI_PIPELINE_FEISHU_TARGET` | `feishu` | `hermes send --to` target |

## Install transcription dep (server only)
```
pip install -r content_pipeline/requirements-pipeline.txt
```

## Add a new 小宇宙 column (onboarding)
1. Append the pid to `TRACKED_PODCASTS` in `podcasts.py` (deploy the backend).
2. **Onboard it once, before the next cron tick** (silent — no Feishu), with the same
   env as the cron (e.g. `VI_TRANSCRIBER=groq`, `GROQ_API_KEY`, `VI_DATABASE_URL`):
   ```
   venv/bin/python -m content_pipeline.backfill_signals --limit 4 <pid> [<pid> …]
   ```
   This **seeds the whole back-catalog as "seen"** (so the daily poll won't back-blast
   it into Feishu) and silently **cards the latest 4 free** episodes for the website.
   Long shows (e.g. 张小珺 runs 2–7h) are why we cap at 4 — Groq chunks each via ffmpeg.
3. From the next tick on, only genuinely NEW episodes push to Feishu (A + B).

⚠️ If you deploy the new pid but skip step 2, the next poll treats the entire catalog
as new and floods Feishu. Don't onboard within ~30 min of 08:00 北京时间 (the cron).

## Add a new source (different site)
Implement `adapters/base.SourceAdapter` (`list_items` + `fetch_media`) in a new
module; nothing else changes. The pipeline is source-agnostic from there on.

## Future: Notion (C)
The 信号卡 schema (`models.REQUIRED_CARD_KEYS`) is pre-aligned to the
`capture_note` contract (情境=播客). Hook the delivered card into the
knowledge-precipitation flywheel to close 子系统 A → B.
