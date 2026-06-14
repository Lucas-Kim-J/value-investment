"""小宇宙 (xiaoyuzhoufm.com) adapter.

The podcast page is a Next.js app embedding one
<script id="__NEXT_DATA__">…</script> JSON blob. Episodes live at
props.pageProps.podcast.episodes[]. Verified against the live page 2026-06-14.
"""
from __future__ import annotations

import json
import re

from content_pipeline.adapters.base import AdapterParseError
from content_pipeline.models import ContentItem

SOURCE = "xiaoyuzhou"
PODCAST_URL = "https://www.xiaoyuzhoufm.com/podcast/{pid}"
EPISODE_URL = "https://www.xiaoyuzhoufm.com/episode/{eid}"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def parse_episodes(html: str, pid: str) -> list[ContentItem]:
    """Parse a podcast page's HTML into ContentItems. Raises AdapterParseError
    if the page has no __NEXT_DATA__, bad JSON, or an unexpected shape."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        raise AdapterParseError("no __NEXT_DATA__ script found")
    try:
        data = json.loads(m.group(1))
        episodes = data["props"]["pageProps"]["podcast"]["episodes"]
    except (ValueError, KeyError, TypeError) as e:
        raise AdapterParseError(f"unexpected __NEXT_DATA__ shape: {e}") from e
    if not isinstance(episodes, list):
        raise AdapterParseError("episodes is not a list")

    items: list[ContentItem] = []
    for ep in episodes:
        eid = ep.get("eid")
        if not eid:
            continue
        items.append(ContentItem(
            source=SOURCE,
            external_id=eid,
            title=ep.get("title", ""),
            url=EPISODE_URL.format(eid=eid),
            published_at=ep.get("pubDate", ""),
            is_paid=(ep.get("payType") != "FREE"),
            media_url=(ep.get("enclosure") or {}).get("url"),
        ))
    return items
