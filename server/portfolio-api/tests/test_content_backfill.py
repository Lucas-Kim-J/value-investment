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


def test_backfill_skips_paid_and_already_carded():
    store = MemoryStore()
    carded = _item("e0")
    store.add(carded)
    store.save_card("xiaoyuzhou", "e0", {"tldr": "existing"})
    adapter = FakeAdapter([carded, _item("e1"), _item("paid", paid=True)])
    tr, dis = FakeTranscriber(), FakeDistiller()
    done = backfill(adapter, store, tr, dis, log=lambda *_: None)
    assert done == 1                       # only e1
    assert dis.calls == ["e1"]             # e0 (carded) + paid skipped
    assert store.get("xiaoyuzhou", "e0")["signal_card"]["tldr"] == "existing"  # untouched
    assert store.get("xiaoyuzhou", "paid") is None


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
