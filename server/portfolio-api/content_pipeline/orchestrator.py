"""Ties the pipeline together: discover new items (send A, skip paid), then
advance each free item through download → transcribe → distill → deliver B.
Idempotent and resumable via the Store state machine. Pure-ish: all I/O is
behind the injected adapter/store/transcriber/distiller/deliverer seams."""
from __future__ import annotations

from content_pipeline.adapters.base import AdapterParseError
from content_pipeline.models import STATUS

MAX_RETRIES = 3


def discover(adapter, store, deliverer):
    """Persist newly-seen items, send the A notice, mark paid vs notified."""
    items = adapter.list_items()            # may raise AdapterParseError
    seen = store.seen_ids(adapter.source)
    for it in items:
        if it.external_id in seen:
            continue
        store.add(it)
        deliverer.send_new_notice(it)       # A — immediate
        if it.is_paid:
            store.set_status(it.source, it.external_id, STATUS.SKIPPED_PAID)
        else:
            store.set_status(it.source, it.external_id, STATUS.NOTIFIED)


def process_item(adapter, item, store, transcriber, distiller, deliverer,
                 max_retries=MAX_RETRIES):
    """Advance one free item to DELIVERED, resuming from saved progress."""
    src, eid = item.source, item.external_id
    try:
        row = store.get(src, eid) or {}
        transcript = row.get("transcript")
        if not transcript:
            store.set_status(src, eid, STATUS.DOWNLOADING)
            audio = adapter.fetch_media(item)
            store.set_status(src, eid, STATUS.TRANSCRIBING)
            transcript = transcriber.transcribe(audio)["text"]
            store.save_transcript(src, eid, transcript)
        card = row.get("signal_card") or distiller.distill(item, transcript)
        store.save_card(src, eid, card)
        store.set_status(src, eid, STATUS.DISTILLED)
        deliverer.send_signal_card(item, card)      # B
        store.set_status(src, eid, STATUS.DELIVERED)
    except Exception as e:  # noqa: BLE001 — any failure is a recoverable per-item error
        count = store.mark_error(src, eid, str(e))
        if count >= max_retries:
            deliverer.send_alert(f"⚠️ 单集多次失败（{count} 次）：{item.title}\n{e}")


def run_once(adapter, store, transcriber, distiller, deliverer, max_retries=MAX_RETRIES):
    """One full poll cycle for a SINGLE feed. Lets AdapterParseError propagate
    (caller alerts)."""
    store.init_schema()
    discover(adapter, store, deliverer)
    for it in store.resumable(adapter.source, max_retries):
        process_item(adapter, it, store, transcriber, distiller, deliverer, max_retries)


def run_many(adapters, store, transcriber, distiller, deliverer, max_retries=MAX_RETRIES):
    """One poll cycle across SEVERAL feeds (e.g. multiple 小宇宙 podcasts that share
    the 'xiaoyuzhou' source). Discover each feed first so every feed's new episodes
    get their A-notice, then run ONE processing pass per distinct source over all
    resumable items — media is fetched by absolute URL, so any adapter of a source
    can fetch any of that source's items.

    A feed whose page can't be parsed (AdapterParseError) is collected and returned
    rather than raised, so one broken feed can't starve the healthy ones. Returns the
    list of (adapter, error) pairs for the caller to alert on (empty = all clean)."""
    store.init_schema()
    errors = []
    for adapter in adapters:
        try:
            discover(adapter, store, deliverer)
        except AdapterParseError as e:
            errors.append((adapter, e))
    fetcher_by_source = {}
    for adapter in adapters:
        fetcher_by_source.setdefault(adapter.source, adapter)
    for source, fetcher in fetcher_by_source.items():
        for it in store.resumable(source, max_retries):
            process_item(fetcher, it, store, transcriber, distiller, deliverer, max_retries)
    return errors
