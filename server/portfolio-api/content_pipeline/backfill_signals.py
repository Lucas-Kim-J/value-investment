#!/usr/bin/env python3
"""One-time SILENT backfill: generate signal cards for already-listed FREE episodes
that don't have one yet — transcribe + distill + store, but NEVER push to Feishu.

Use it to populate the website's history without spamming the Feishu feed with a
burst of old cards. Resumable: a saved transcript is reused, an existing card skips
the episode. Bounded to the episodes currently embedded on the podcast page (~15).

Run on the server (real whisper + hermes + PG):
    venv/bin/python -m content_pipeline.backfill_signals            # all that need cards
    venv/bin/python -m content_pipeline.backfill_signals --limit 1  # validate one first
"""
from __future__ import annotations

import argparse
import os

from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.distiller import Distiller
from content_pipeline.models import STATUS
from content_pipeline.store import PgStore
from content_pipeline.transcriber import Transcriber


def backfill(adapter, store, transcriber, distiller, limit: int = 0, log=print) -> int:
    """Generate + store a signal card for each free, card-less episode. No delivery
    (the absence of a deliverer is what makes this silent). Returns count carded."""
    store.init_schema()
    items = [it for it in adapter.list_items() if not it.is_paid]
    todo = [it for it in items
            if not (store.get(it.source, it.external_id) or {}).get("signal_card")]
    if limit:
        todo = todo[:limit]
    log(f"backfill: {len(todo)} free episode(s) need a card (of {len(items)} free listed)")
    done = 0
    for it in todo:
        try:
            store.add(it)  # ensure row + carry image_url/show_title (ON CONFLICT DO NOTHING)
            row = store.get(it.source, it.external_id) or {}
            transcript = row.get("transcript")
            if not transcript:
                store.set_status(it.source, it.external_id, STATUS.TRANSCRIBING)
                transcript = transcriber.transcribe(adapter.fetch_media(it))["text"]
                store.save_transcript(it.source, it.external_id, transcript)
            card = row.get("signal_card") or distiller.distill(it, transcript)
            store.save_card(it.source, it.external_id, card)
            store.set_status(it.source, it.external_id, STATUS.DELIVERED)
            done += 1
            log(f"  [{done}/{len(todo)}] carded: {it.title[:42]}")
        except Exception as e:  # noqa: BLE001 — keep going; failed one stays retryable
            store.mark_error(it.source, it.external_id, str(e))
            log(f"  ERROR {it.external_id}: {str(e)[:120]}")
    log(f"backfill done: {done}/{len(todo)} carded (no Feishu push)")
    return done


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Silent signal-card backfill (no Feishu)")
    parser.add_argument("--limit", type=int, default=0, help="max episodes (0 = all that need it)")
    args = parser.parse_args(argv)
    pid = os.environ.get("VI_PIPELINE_PODCAST_ID", "6978a31df828d4e9f2787d3d")
    backfill(XiaoyuzhouAdapter(pid), PgStore(), Transcriber(), Distiller(), limit=args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
