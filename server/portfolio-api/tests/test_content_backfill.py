from content_pipeline.models import ContentItem, STATUS
from content_pipeline.store import MemoryStore
from content_pipeline.backfill_signals import backfill


def _item(eid, paid=False):
    return ContentItem(source="xiaoyuzhou", external_id=eid, title=f"T{eid}",
                       url=f"u/{eid}", published_at="2026-06-13T16:00:00.000Z",
                       is_paid=paid, media_url=f"m/{eid}")


class FakeAdapter:
    source = "xiaoyuzhou"

    def __init__(self, items):
        self._items = items
        self.fetched = []

    def list_items(self):
        return list(self._items)

    def fetch_media(self, item):
        self.fetched.append(item.external_id)
        return f"/tmp/{item.external_id}.m4a"


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(self, path):
        self.calls.append(path)
        return {"text": f"transcript-of-{path}", "segments": []}


class FakeDistiller:
    def __init__(self):
        self.calls = []

    def distill(self, item, transcript):
        self.calls.append(item.external_id)
        return {"tldr": "t", "non_consensus": "n", "new_angle": "a", "pillar": "资金传导",
                "caution": "c", "worth_relisten": {"yes": False, "timestamps": []}}


def test_backfill_cards_free_cardless_episodes_silently():
    store = MemoryStore()
    adapter = FakeAdapter([_item("e1"), _item("e2")])
    tr, dis = FakeTranscriber(), FakeDistiller()
    done = backfill(adapter, store, tr, dis, log=lambda *_: None)
    assert done == 2
    for eid in ("e1", "e2"):
        row = store.get("xiaoyuzhou", eid)
        assert row["signal_card"]["pillar"] == "资金传导"
        assert row["status"] == STATUS.DELIVERED
    # silent = it never had a deliverer; transcription + distill happened
    assert tr.calls and dis.calls == ["e1", "e2"]


def test_backfill_seeds_all_then_cards_free_cardless():
    store = MemoryStore()
    carded = _item("e0")
    store.add(carded)
    store.save_card("xiaoyuzhou", "e0", {"tldr": "existing"})
    adapter = FakeAdapter([carded, _item("e1"), _item("paid", paid=True)])
    tr, dis = FakeTranscriber(), FakeDistiller()
    done = backfill(adapter, store, tr, dis, log=lambda *_: None)
    assert done == 1                       # only e1 carded
    assert dis.calls == ["e1"]             # e0 (already carded) + paid skipped
    assert store.get("xiaoyuzhou", "e0")["signal_card"]["tldr"] == "existing"  # untouched
    # paid is now SEEDED (a row marks it 'seen') but never carded — so the daily
    # poll won't later treat it as new, yet it stays off the website (no card).
    paid = store.get("xiaoyuzhou", "paid")
    assert paid is not None and paid["signal_card"] is None


def test_backfill_seeds_whole_catalog_even_beyond_limit():
    # 5 free episodes, card only the latest 2 — but ALL 5 must be seeded so the daily
    # poll never back-blasts the other 3 into Feishu as "new".
    store = MemoryStore()
    eps = [_item(f"e{i}") for i in range(5)]
    done = backfill(FakeAdapter(eps), store, FakeTranscriber(), FakeDistiller(),
                    limit=2, log=lambda *_: None)
    assert done == 2
    assert len(store.seen_ids("xiaoyuzhou")) == 5          # every episode seeded
    carded = [e.external_id for e in eps
              if store.get("xiaoyuzhou", e.external_id)["signal_card"]]
    assert len(carded) == 2                                # only 2 carded, 3 seeded-but-cardless


def test_backfill_limit_caps_work():
    store = MemoryStore()
    adapter = FakeAdapter([_item("e1"), _item("e2"), _item("e3")])
    done = backfill(adapter, store, FakeTranscriber(), FakeDistiller(), limit=1, log=lambda *_: None)
    assert done == 1


def test_backfill_reuses_saved_transcript_on_rerun():
    store = MemoryStore()
    it = _item("e1")
    store.add(it)
    store.save_transcript("xiaoyuzhou", "e1", "已有转录")
    adapter = FakeAdapter([it])
    tr, dis = FakeTranscriber(), FakeDistiller()
    backfill(adapter, store, tr, dis, log=lambda *_: None)
    assert tr.calls == []                  # did NOT re-transcribe
    assert dis.calls == ["e1"]             # distilled from the saved transcript
