"""Tracked 小宇宙 podcast feeds — single source of truth for `run` + `backfill`.

Each pid is polled daily; the per-episode `show_title` and cover art are
auto-discovered off the page by the adapter, so the names below are only for
readability/logs. To add a column: append its pid here (and onboard it once with
`backfill_signals` so the daily poll doesn't back-blast its whole catalog)."""
from __future__ import annotations

import os

# pid -> human name (display name is read live from the page; this is documentation).
TRACKED_PODCASTS = {
    "6978a31df828d4e9f2787d3d": "非共识的20分钟",
    "626b46ea9cbbf0451cf5a962": "张小珺Jùn｜商业访谈录",
    "65539db173f6183e975cfccc": "The Wanderers 流浪者",
}


def podcast_ids() -> list[str]:
    """The feeds to poll. Override with VI_PIPELINE_PODCAST_IDS (comma-separated);
    the legacy singular VI_PIPELINE_PODCAST_ID is still honoured. Falls back to the
    tracked defaults above."""
    raw = os.environ.get("VI_PIPELINE_PODCAST_IDS") or os.environ.get("VI_PIPELINE_PODCAST_ID")
    if raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return list(TRACKED_PODCASTS)
