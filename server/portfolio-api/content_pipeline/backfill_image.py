#!/usr/bin/env python3
"""One-time backfill: set image_url + show_title on existing content_items rows
from the live podcast page. Safe to re-run (idempotent UPDATE by key). Run on the
server with VI_DATABASE_URL set: `venv/bin/python -m content_pipeline.backfill_image`."""
from __future__ import annotations

import os

from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.store import _db  # reuse the same connection contextmanager


def main() -> int:
    pid = os.environ.get("VI_PIPELINE_PODCAST_ID", "6978a31df828d4e9f2787d3d")
    items = XiaoyuzhouAdapter(pid).list_items()
    n = 0
    with _db() as c, c.cursor() as cur:
        for it in items:
            cur.execute(
                "UPDATE content_items SET image_url=COALESCE(image_url,%s), "
                "show_title=COALESCE(show_title,%s) WHERE source=%s AND external_id=%s",
                (it.image_url, it.show_title, it.source, it.external_id))
            n += cur.rowcount
    print(f"backfilled {n} rows (image_url/show_title where missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
