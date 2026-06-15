import json
import pytest

from content_pipeline.adapters.xiaoyuzhou import parse_episodes, EPISODE_URL
from content_pipeline.adapters.base import AdapterParseError

PID = "6978a31df828d4e9f2787d3d"
from content_pipeline.adapters.xiaoyuzhou import PODCAST_URL
from content_pipeline.models import ContentItem
PODCAST_URL_FOR_TEST = PODCAST_URL.format(pid=PID)


def _page(episodes):
    """Build a minimal page with the real __NEXT_DATA__ shape."""
    payload = {"props": {"pageProps": {"podcast": {"episodes": episodes}}}}
    return (
        "<html><body>"
        f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
        "</body></html>"
    )


def test_parses_free_episode_into_content_item():
    html = _page([{
        "eid": "abc123", "title": "Ep 9 | 测试",
        "pubDate": "2026-06-13T16:00:00.000Z", "duration": 590, "payType": "FREE",
        "enclosure": {"url": "https://media.xyzcdn.net/x/abc123.m4a"},
    }])
    items = parse_episodes(html, PID)
    assert len(items) == 1
    it = items[0]
    assert it.source == "xiaoyuzhou"
    assert it.external_id == "abc123"
    assert it.title == "Ep 9 | 测试"
    assert it.is_paid is False
    assert it.media_url == "https://media.xyzcdn.net/x/abc123.m4a"
    assert it.url == EPISODE_URL.format(eid="abc123")
    assert it.published_at == "2026-06-13T16:00:00.000Z"


def test_marks_paid_episode():
    html = _page([{
        "eid": "pay1", "title": "付费集", "pubDate": "2026-06-12T00:00:00.000Z",
        "payType": "PAY_EPISODE", "enclosure": {"url": "https://media.xyzcdn.net/x/pay1.m4a"},
    }])
    items = parse_episodes(html, PID)
    assert items[0].is_paid is True


def test_missing_enclosure_yields_none_media_url_but_still_parses():
    html = _page([{"eid": "noaudio", "title": "X", "pubDate": "2026-06-12T00:00:00.000Z",
                   "payType": "FREE"}])
    items = parse_episodes(html, PID)
    assert items[0].media_url is None


def test_no_next_data_raises_adapter_parse_error():
    with pytest.raises(AdapterParseError):
        parse_episodes("<html><body>no script here</body></html>", PID)


def test_malformed_json_raises_adapter_parse_error():
    html = '<script id="__NEXT_DATA__" type="application/json">{not json}</script>'
    with pytest.raises(AdapterParseError):
        parse_episodes(html, PID)


def test_unexpected_shape_raises_adapter_parse_error():
    html = '<script id="__NEXT_DATA__" type="application/json">{"props":{}}</script>'
    with pytest.raises(AdapterParseError):
        parse_episodes(html, PID)


from pathlib import Path
from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter


def test_list_items_uses_injected_fetcher():
    html = _page([{"eid": "z1", "title": "Z", "pubDate": "2026-06-13T16:00:00.000Z",
                   "payType": "FREE", "enclosure": {"url": "https://m/z1.m4a"}}])
    calls = {}

    def fake_get(url):
        calls["url"] = url
        return html.encode("utf-8")

    ad = XiaoyuzhouAdapter(PID, http_get=fake_get)
    items = ad.list_items()
    assert ad.source == "xiaoyuzhou"
    assert calls["url"] == PODCAST_URL_FOR_TEST
    assert items[0].external_id == "z1"


def test_fetch_media_writes_audio_to_tmp(tmp_path):
    def fake_get(url):
        return b"FAKEAUDIOBYTES"

    ad = XiaoyuzhouAdapter(PID, http_get=fake_get, tmp_dir=tmp_path)
    it = ContentItem(source="xiaoyuzhou", external_id="z1", title="Z",
                     url="u", published_at="p", is_paid=False,
                     media_url="https://m/z1.m4a")
    path = ad.fetch_media(it)
    assert Path(path).read_bytes() == b"FAKEAUDIOBYTES"


def test_fetch_media_without_media_url_raises():
    ad = XiaoyuzhouAdapter(PID, http_get=lambda u: b"")
    it = ContentItem(source="xiaoyuzhou", external_id="z1", title="Z",
                     url="u", published_at="p", is_paid=True, media_url=None)
    with pytest.raises(ValueError):
        ad.fetch_media(it)


def test_parses_show_title_and_cover_image():
    payload = {"props": {"pageProps": {"podcast": {
        "title": "非共识的20分钟",
        "image": {"middlePicUrl": "https://image.xyzcdn.net/cover.jpg@middle"},
        "episodes": [{
            "eid": "e9", "title": "Ep 9", "pubDate": "2026-06-13T16:00:00.000Z",
            "payType": "FREE", "enclosure": {"url": "https://m/e9.m4a"},
        }],
    }}}}
    import json as _json
    html = f'<script id="__NEXT_DATA__" type="application/json">{_json.dumps(payload)}</script>'
    items = parse_episodes(html, PID)
    assert items[0].show_title == "非共识的20分钟"
    assert items[0].image_url == "https://image.xyzcdn.net/cover.jpg@middle"


def test_parses_missing_image_as_none():
    payload = {"props": {"pageProps": {"podcast": {
        "title": "X", "episodes": [{"eid": "e1", "title": "T",
            "pubDate": "2026-06-12T00:00:00.000Z", "payType": "FREE"}]}}}}
    import json as _json
    html = f'<script id="__NEXT_DATA__" type="application/json">{_json.dumps(payload)}</script>'
    items = parse_episodes(html, PID)
    assert items[0].image_url is None
    assert items[0].show_title == "X"
