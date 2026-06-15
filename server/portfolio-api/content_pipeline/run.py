#!/usr/bin/env python3
"""Cron entrypoint for the content signal pipeline.

Run ON THE SERVER (hermes + PostgreSQL + faster-whisper). Wires the real
components and runs one poll cycle. Schedule daily at 08:00 北京时间 (= UTC 00:00).

Usage:
    python -m content_pipeline.run            # one real cycle
    python -m content_pipeline.run --dry-run  # mock whisper+hermes, no DB:
                                              # uses MemoryStore + mock modes, prints actions
"""
from __future__ import annotations

import argparse
import sys

from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.deliverer import Deliverer
from content_pipeline.distiller import Distiller
from content_pipeline.podcasts import podcast_ids
from content_pipeline.transcriber import Transcriber, make_transcriber
from content_pipeline import orchestrator


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Content signal pipeline — one poll cycle")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mock whisper+hermes, in-memory store, print actions only")
    args = parser.parse_args(argv)

    adapters = [XiaoyuzhouAdapter(pid) for pid in podcast_ids()]

    if args.dry_run:
        from content_pipeline.store import MemoryStore
        store = MemoryStore()
        transcriber = Transcriber(mode="mock")
        distiller = Distiller(runner=lambda p: '{"tldr":"(dry)","non_consensus":"-",'
                              '"new_angle":"-","pillar":"无","caution":"-",'
                              '"worth_relisten":{"yes":false,"timestamps":[]}}')

        class _PrintDeliverer:
            def send_new_notice(self, it): print(f"[A] {it.title} ({'PAID' if it.is_paid else 'free'})")
            def send_signal_card(self, it, card): print(f"[B] {it.title} -> {card}")
            def send_alert(self, text): print(f"[ALERT] {text}")
        deliverer = _PrintDeliverer()
    else:
        from content_pipeline.store import PgStore
        store = PgStore()
        transcriber = make_transcriber()   # VI_TRANSCRIBER=groq → Groq + local fallback
        distiller = Distiller()
        deliverer = Deliverer()

    errors = orchestrator.run_many(adapters, store, transcriber, distiller, deliverer)
    for adapter, e in errors:
        msg = f"⚠️ 适配器需修（{adapter.source}/{getattr(adapter, 'podcast_id', '?')}）：{e}"
        print(msg, file=sys.stderr)
        try:
            deliverer.send_alert(msg)
        except Exception:  # noqa: BLE001
            pass
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
