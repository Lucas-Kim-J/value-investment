import pytest

from content_pipeline.models import ContentItem, STATUS
from content_pipeline.adapters.base import AdapterParseError
from content_pipeline.store import MemoryStore
from content_pipeline import orchestrator


# ---- inline component fakes (only used here) ----

class FakeAdapter:
    source = "xiaoyuzhou"

    def __init__(self, items, raise_on_list=False):
        self._items = items
        self._raise = raise_on_list
        self.fetched = []

    def list_items(self):
        if self._raise:
            raise AdapterParseError("structure changed")
        return list(self._items)

    def fetch_media(self, item):
        self.fetched.append(item.external_id)
        return f"/tmp/{item.external_id}.m4a"


class FakeTranscriber:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def transcribe(self, path):
        self.calls.append(path)
        if self.fail:
            raise RuntimeError("whisper boom")
        return {"text": f"transcript-of-{path}", "segments": []}


class FakeDistiller:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    def distill(self, item, transcript):
        self.calls.append((item.external_id, transcript))
        if self.fail:
            raise RuntimeError("distill boom")
        return {"tldr": "t", "non_consensus": "n", "new_angle": "a",
                "pillar": "资金传导", "caution": "c",
                "worth_relisten": {"yes": False, "timestamps": []}}


class FakeDeliverer:
    def __init__(self):
        self.notices = []
        self.cards = []
        self.alerts = []

    def send_new_notice(self, item):
        self.notices.append(item.external_id)

    def send_signal_card(self, item, card):
        self.cards.append((item.external_id, card))

    def send_alert(self, text):
        self.alerts.append(text)


# ---- tests ----

def _item(eid, paid=False):
    return ContentItem(source="xiaoyuzhou", external_id=eid, title=f"T{eid}",
                       url=f"u/{eid}", published_at="2026-06-13T16:00:00.000Z",
                       is_paid=paid, media_url=f"m/{eid}")


def _run(adapter, store, tr, dis, deliv):
    orchestrator.run_once(adapter, store, tr, dis, deliv)


def test_free_episode_happy_path_reaches_delivered():
    store = MemoryStore()
    adapter = FakeAdapter([_item("a")])
    deliv = FakeDeliverer()
    _run(adapter, store, FakeTranscriber(), FakeDistiller(), deliv)
    assert store.get("xiaoyuzhou", "a")["status"] == STATUS.DELIVERED
    assert deliv.notices == ["a"]              # A sent
    assert deliv.cards[0][0] == "a"            # B sent
    assert store.get("xiaoyuzhou", "a")["transcript"] == "transcript-of-/tmp/a.m4a"


def test_paid_episode_only_notifies_and_skips():
    store = MemoryStore()
    adapter = FakeAdapter([_item("p", paid=True)])
    tr, dis, deliv = FakeTranscriber(), FakeDistiller(), FakeDeliverer()
    _run(adapter, store, tr, dis, deliv)
    assert store.get("xiaoyuzhou", "p")["status"] == STATUS.SKIPPED_PAID
    assert deliv.notices == ["p"]
    assert deliv.cards == []
    assert tr.calls == []                      # never transcribed


def test_dedup_skips_already_seen():
    store = MemoryStore()
    store.add(_item("a")); store.set_status("xiaoyuzhou", "a", STATUS.DELIVERED)
    adapter = FakeAdapter([_item("a")])
    deliv = FakeDeliverer()
    _run(adapter, store, FakeTranscriber(), FakeDistiller(), deliv)
    assert deliv.notices == []                 # no duplicate A
    assert deliv.cards == []


def test_distill_failure_marks_error_but_keeps_transcript():
    store = MemoryStore()
    adapter = FakeAdapter([_item("a")])
    _run(adapter, store, FakeTranscriber(), FakeDistiller(fail=True), FakeDeliverer())
    row = store.get("xiaoyuzhou", "a")
    assert row["status"] == STATUS.ERROR
    assert row["transcript"] == "transcript-of-/tmp/a.m4a"   # not wasted
    assert row["error_count"] == 1


def test_retry_resumes_from_distill_without_retranscribing():
    store = MemoryStore()
    # first run: distill fails, transcript saved, status error
    adapter = FakeAdapter([_item("a")])
    tr1 = FakeTranscriber()
    _run(adapter, store, tr1, FakeDistiller(fail=True), FakeDeliverer())
    assert tr1.calls  # transcribed once
    # second run: same episode already seen; resumable picks the errored item
    tr2 = FakeTranscriber()
    _run(adapter, store, tr2, FakeDistiller(), FakeDeliverer())
    assert tr2.calls == []                     # did NOT re-transcribe
    assert store.get("xiaoyuzhou", "a")["status"] == STATUS.DELIVERED


def test_max_retries_sends_alert_and_stops():
    store = MemoryStore()
    adapter = FakeAdapter([_item("a")])
    deliv = FakeDeliverer()
    # 3 failing runs reach max_retries=3
    for _ in range(3):
        _run(adapter, store, FakeTranscriber(), FakeDistiller(fail=True), deliv)
    assert store.get("xiaoyuzhou", "a")["error_count"] == 3
    assert deliv.alerts                        # alerted on hitting the cap
    # 4th run: no longer resumable, no further work
    deliv2 = FakeDeliverer()
    _run(adapter, store, FakeTranscriber(), FakeDistiller(), deliv2)
    assert store.get("xiaoyuzhou", "a")["status"] == STATUS.ERROR


def test_adapter_parse_error_propagates():
    store = MemoryStore()
    adapter = FakeAdapter([], raise_on_list=True)
    with pytest.raises(AdapterParseError):
        _run(adapter, store, FakeTranscriber(), FakeDistiller(), FakeDeliverer())


# ---- run_many: multiple feeds sharing one source ----

def test_run_many_discovers_each_feed_then_processes_once():
    store = MemoryStore()
    feed1 = FakeAdapter([_item("a"), _item("b")])
    feed2 = FakeAdapter([_item("c", paid=True), _item("d")])
    deliv = FakeDeliverer()
    errors = orchestrator.run_many([feed1, feed2], store,
                                   FakeTranscriber(), FakeDistiller(), deliv)
    assert errors == []
    assert set(deliv.notices) == {"a", "b", "c", "d"}      # every feed's new episodes A-noticed
    for eid in ("a", "b", "d"):
        assert store.get("xiaoyuzhou", eid)["status"] == STATUS.DELIVERED
    assert store.get("xiaoyuzhou", "c")["status"] == STATUS.SKIPPED_PAID


def test_run_many_isolates_a_broken_feed():
    store = MemoryStore()
    good = FakeAdapter([_item("g")])
    bad = FakeAdapter([], raise_on_list=True)
    deliv = FakeDeliverer()
    errors = orchestrator.run_many([good, bad], store,
                                   FakeTranscriber(), FakeDistiller(), deliv)
    assert len(errors) == 1 and errors[0][0] is bad        # broken feed reported, not raised
    assert store.get("xiaoyuzhou", "g")["status"] == STATUS.DELIVERED   # healthy feed still ran
    assert "g" in deliv.notices
