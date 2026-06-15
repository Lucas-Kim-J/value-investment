#!/usr/bin/env python3
"""One-time ONBOARD / SILENT backfill for 小宇宙 podcast feeds.

Two jobs, both without ever pushing to Feishu (the absence of a deliverer is what
makes it silent — so the website's history gets populated without spamming the feed):

  1. SEED the back-catalog: insert a row for EVERY currently-listed episode (free
     AND paid). Once a row exists the daily poll treats it as "seen" and won't fire
     an A-notice for it — this is what stops a newly-tracked podcast from back-blasting
     its entire history into Feishu on the next cron tick.
  2. CARD the latest `--limit` FREE, card-less episodes (transcribe + distill + store).
     `--limit 0` cards them all (used for the original 非共识 backfill).

Resumable: a saved transcript is reused, an existing card skips the episode.

Run on the server (real whisper/Groq + hermes + PG), with the SAME env as the cron
(e.g. VI_TRANSCRIBER=groq, GROQ_API_KEY, VI_DATABASE_URL):

    # onboard the two long-form podcasts, 4 newest free episodes each:
    venv/bin/python -m content_pipeline.backfill_signals --limit 4 \
        626b46ea9cbbf0451cf5a962 65539db173f6183e975cfccc

    venv/bin/python -m content_pipeline.backfill_signals --limit 1 <pid>   # validate one first
    venv/bin/python -m content_pipeline.backfill_signals                   # all tracked, all free
"""
from __future__ import annotations

import argparse

from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.distiller import Distiller
from content_pipeline.models import STATUS
from content_pipeline.podcasts import podcast_ids
from content_pipeline.store import PgStore
from content_pipeline.transcriber import make_transcriber


def backfill(adapter, store, transcriber, distiller, limit: int = 0, log=print) -> int:
    """Seed every listed episode as 'seen', then card the latest `limit` free, card-less
    ones (0 = all free). No delivery. Returns the count carded."""
    store.init_schema()
    items = adapter.list_items()
    # 1) Seed the whole catalog so the daily poll never back-blasts it as "new".
    #    ON CONFLICT DO NOTHING keeps already-known rows (and their cards) untouched.
    for it in items:
        store.add(it)
    free = [it for it in items if not it.is_paid]
    todo = [it for it in free
            if not (store.get(it.source, it.external_id) or {}).get("signal_card")]
    if limit:
        todo = todo[:limit]            # free list is newest-first → the latest N
    log(f"backfill: seeded {len(items)} listed episode(s) as seen; "
        f"carding {len(todo)} latest free (of {len(free)} free listed)")
    done = 0
    for it in todo:
        try:
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
    parser = argparse.ArgumentParser(description="Silent onboard/backfill (seed catalog + card N, no Feishu)")
    parser.add_argument("--limit", type=int, default=0,
                        help="max episodes to card PER podcast (0 = all free)")
    parser.add_argument("pids", nargs="*",
                        help="podcast id(s) to onboard (default: all tracked / env)")
    args = parser.parse_args(argv)

    pids = args.pids or podcast_ids()
    store, transcriber, distiller = PgStore(), make_transcriber(), Distiller()
    total = 0
    for pid in pids:
        print(f"\n=== backfill {pid} (limit={args.limit or 'all free'}) ===")
        total += backfill(XiaoyuzhouAdapter(pid), store, transcriber, distiller, limit=args.limit)
    print(f"\nALL done: {total} card(s) across {len(pids)} podcast(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
