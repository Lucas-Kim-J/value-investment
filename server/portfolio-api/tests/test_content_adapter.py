import json
import pytest

from content_pipeline.adapters.xiaoyuzhou import parse_episodes, EPISODE_URL
from content_pipeline.adapters.base import AdapterParseError

PID = "6978a31df828d4e9f2787d3d"


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
