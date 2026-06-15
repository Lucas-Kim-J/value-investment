from content_pipeline.models import ContentItem, STATUS, PILLARS


def test_content_item_holds_source_fields():
    it = ContentItem(
        source="xiaoyuzhou", external_id="e1", title="T",
        url="https://x/episode/e1", published_at="2026-06-13T16:00:00.000Z",
        is_paid=False, media_url="https://m/e1.m4a",
    )
    assert it.source == "xiaoyuzhou"
    assert it.external_id == "e1"
    assert it.is_paid is False
    assert it.media_url.endswith(".m4a")


def test_status_constants_are_distinct_strings():
    vals = [STATUS.NEW, STATUS.NOTIFIED, STATUS.DOWNLOADING, STATUS.TRANSCRIBING,
            STATUS.DISTILLED, STATUS.DELIVERED, STATUS.SKIPPED_PAID, STATUS.ERROR]
    assert len(set(vals)) == len(vals)
    assert STATUS.SKIPPED_PAID == "skipped_paid"


def test_pillars_enumeration():
    assert "第一性原理" in PILLARS
    assert "无" in PILLARS


def test_content_item_carries_image_and_show_title():
    it = ContentItem(
        source="xiaoyuzhou", external_id="e1", title="T", url="u",
        published_at="2026-06-13T16:00:00.000Z", is_paid=False, media_url="m",
        image_url="https://image.xyzcdn.net/x.jpg", show_title="非共识的20分钟",
    )
    assert it.image_url.endswith(".jpg")
    assert it.show_title == "非共识的20分钟"


def test_content_item_image_and_show_default_none():
    it = ContentItem(source="s", external_id="e", title="T", url="u", published_at="p")
    assert it.image_url is None
    assert it.show_title is None
