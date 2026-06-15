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

    podcast = data["props"]["pageProps"]["podcast"]
    show_title = podcast.get("title")
    image_url = (podcast.get("image") or {}).get("middlePicUrl")

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
            image_url=image_url,
            show_title=show_title,
        ))
    return items


import tempfile
import urllib.request
from pathlib import Path

_HTTP_TIMEOUT = 20
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as r:
        return r.read()


class XiaoyuzhouAdapter:
    """SourceAdapter for 小宇宙. http_get is injectable for tests."""
    source = SOURCE

    def __init__(self, podcast_id: str, http_get=_default_http_get, tmp_dir=None):
        self.podcast_id = podcast_id
        self._get = http_get
        self._tmp_dir = Path(tmp_dir) if tmp_dir else Path(tempfile.gettempdir())

    def list_items(self) -> list[ContentItem]:
        html = self._get(PODCAST_URL.format(pid=self.podcast_id)).decode("utf-8", "replace")
        return parse_episodes(html, self.podcast_id)

    def fetch_media(self, item: ContentItem) -> Path:
        if not item.media_url:
            raise ValueError(f"item {item.external_id} has no media_url")
        data = self._get(item.media_url)
        out = self._tmp_dir / f"{item.source}_{item.external_id}.m4a"
        out.write_bytes(data)
        return out
