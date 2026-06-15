import os
import pytest

from content_pipeline.models import ContentItem, STATUS
from content_pipeline.store import MemoryStore


def _item(eid, paid=False):
    return ContentItem(source="xiaoyuzhou", external_id=eid, title=f"T{eid}",
                       url=f"u/{eid}", published_at="2026-06-13T16:00:00.000Z",
                       is_paid=paid, media_url=f"m/{eid}")


def test_add_and_seen_ids():
    s = MemoryStore()
    s.add(_item("a"))
    s.add(_item("b"))
    assert s.seen_ids("xiaoyuzhou") == {"a", "b"}
    assert s.seen_ids("other") == set()


def test_new_item_starts_new_status():
    s = MemoryStore(); s.add(_item("a"))
    assert s.get("xiaoyuzhou", "a")["status"] == STATUS.NEW


def test_set_status_and_save_transcript_and_card():
    s = MemoryStore(); s.add(_item("a"))
    s.set_status("xiaoyuzhou", "a", STATUS.TRANSCRIBING)
    s.save_transcript("xiaoyuzhou", "a", "全文")
    s.save_card("xiaoyuzhou", "a", {"tldr": "x"})
    row = s.get("xiaoyuzhou", "a")
    assert row["status"] == STATUS.TRANSCRIBING
    assert row["transcript"] == "全文"
    assert row["signal_card"]["tldr"] == "x"


def test_mark_error_increments_count():
    s = MemoryStore(); s.add(_item("a"))
    assert s.mark_error("xiaoyuzhou", "a", "boom") == 1
    assert s.mark_error("xiaoyuzhou", "a", "boom") == 2
    assert s.get("xiaoyuzhou", "a")["status"] == STATUS.ERROR


def test_resumable_includes_notified_and_retryable_error_excludes_terminal():
    s = MemoryStore()
    s.add(_item("notif")); s.set_status("xiaoyuzhou", "notif", STATUS.NOTIFIED)
    s.add(_item("done")); s.set_status("xiaoyuzhou", "done", STATUS.DELIVERED)
    s.add(_item("paid", paid=True)); s.set_status("xiaoyuzhou", "paid", STATUS.SKIPPED_PAID)
    s.add(_item("err")); s.mark_error("xiaoyuzhou", "err", "x")  # count=1
    s.add(_item("dead"))
    for _ in range(3):
        s.mark_error("xiaoyuzhou", "dead", "x")  # count=3 -> at max
    ids = {it.external_id for it in s.resumable("xiaoyuzhou", max_retries=3)}
    assert ids == {"notif", "err"}


def test_resumable_returns_content_items_with_media_url():
    s = MemoryStore(); s.add(_item("a")); s.set_status("xiaoyuzhou", "a", STATUS.NOTIFIED)
    [it] = s.resumable("xiaoyuzhou", max_retries=3)
    assert isinstance(it, ContentItem)
    assert it.media_url == "m/a"


@pytest.mark.skipif(not os.environ.get("VI_DATABASE_URL"), reason="no VI_DATABASE_URL")
def test_pgstore_roundtrip():
    from content_pipeline.store import PgStore
    s = PgStore(); s.init_schema()
    s.add(_item("smoke-1"))
    assert "smoke-1" in s.seen_ids("xiaoyuzhou")
    s.set_status("xiaoyuzhou", "smoke-1", STATUS.NOTIFIED)
    assert any(i.external_id == "smoke-1" for i in s.resumable("xiaoyuzhou"))


def test_memorystore_persists_image_and_show_title():
    s = MemoryStore()
    it = ContentItem(source="xiaoyuzhou", external_id="a", title="T", url="u",
                     published_at="2026-06-13T16:00:00.000Z", is_paid=False, media_url="m",
                     image_url="https://image/x.jpg", show_title="非共识的20分钟")
    s.add(it)
    row = s.get("xiaoyuzhou", "a")
    assert row["image_url"] == "https://image/x.jpg"
    assert row["show_title"] == "非共识的20分钟"
