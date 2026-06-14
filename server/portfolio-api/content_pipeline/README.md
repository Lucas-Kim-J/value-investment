# Content Signal Pipeline (子系统 A 第一实现)

Daily: detect new 小宇宙 episodes → Feishu notice (A) → transcribe + distill free
episodes into a 信号卡 (B). Source-agnostic behind `adapters/SourceAdapter`.

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
| `VI_PIPELINE_PODCAST_ID` | `6978a31df828d4e9f2787d3d` | 小宇宙 pid to poll |
| `VI_WHISPER_MODE` | `whisper` | `mock` to skip the model |
| `VI_PIPELINE_PROFILE` | `app-lucas` | hermes profile for the distill skill |
| `VI_PIPELINE_FEISHU_TARGET` | `feishu` | `hermes send --to` target |

## Install transcription dep (server only)
```
pip install -r content_pipeline/requirements-pipeline.txt
```

## Add a new source
Implement `adapters/base.SourceAdapter` (`list_items` + `fetch_media`) in a new
module; nothing else changes. The pipeline is source-agnostic from there on.

## Future: Notion (C)
The 信号卡 schema (`models.REQUIRED_CARD_KEYS`) is pre-aligned to the
`capture_note` contract (情境=播客). Hook the delivered card into the
knowledge-precipitation flywheel to close 子系统 A → B.
