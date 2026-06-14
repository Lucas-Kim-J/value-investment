# Content Signal Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily cron pipeline that detects new 小宇宙 podcast episodes, pushes a Feishu notice (A), then transcribes + distills free episodes into a structured 信号卡 delivered to Feishu (B) — built behind a source-agnostic adapter interface so new content sources are plug-in.

**Architecture:** A self-contained Python package `server/portfolio-api/content_pipeline/`. A `SourceAdapter` interface (the "架子") is the only source-coupled seam; everything downstream (transcribe → distill → deliver → store) is source-agnostic. A PostgreSQL table `content_items` gives dedup + a status state machine so the daily run is idempotent and resumes after failures. All pure logic (HTML parsing, prompt building, card parsing, rendering, state transitions over a `Store` protocol) is unit-tested with in-memory fakes — matching the repo's existing `capture.py` + `FakeNotionClient` pattern. I/O wrappers (urllib HTTP, faster-whisper, `hermes` subprocess, psycopg2) are thin and run in a `mock` mode locally.

**Tech Stack:** Python 3, stdlib `urllib` (HTTP — repo convention, no `requests`), `psycopg2` (PostgreSQL), `faster-whisper` (transcription, lazy-imported), `hermes` CLI via `subprocess` (LLM skill + Feishu delivery), `pytest`.

---

## Verified reference: 小宇宙 `__NEXT_DATA__` shape (captured live 2026-06-14)

The podcast page `https://www.xiaoyuzhoufm.com/podcast/<pid>` embeds one `<script id="__NEXT_DATA__" type="application/json">…</script>`. Episodes live at:

```
data["props"]["pageProps"]["podcast"]["episodes"]   # list, latest ~15
```

Each episode object (fields we use):

```json
{
  "eid": "6a2d2cec4233e62bc5492b1e",
  "title": "美联储长青系列Ep 7 | …",
  "pubDate": "2026-06-13T16:00:00.000Z",
  "duration": 590,
  "payType": "FREE",                       // or "PAY_EPISODE" / "PAY_EPISODE_PODCAST"
  "enclosure": { "url": "https://media.xyzcdn.net/<pid>/<key>.m4a" }
}
```

- **Paid detection:** `payType != "FREE"` → paid (skip transcription).
- **Audio:** `episode["enclosure"]["url"]`.
- **Episode link:** `https://www.xiaoyuzhoufm.com/episode/<eid>`.
- Target podcast 《非共识的20分钟》 pid = `6978a31df828d4e9f2787d3d`.
- Only the latest ~15 episodes are embedded — sufficient for a daily poll (host posts ~1–2/day). If >15 free episodes ever drop in one day, the surplus is missed; the run logs the embedded count so this bound is visible (no silent truncation).

---

## File Structure

Created (all new, additive — nothing existing is modified except adding a deferred-items resolution note to the spec in the final task):

```
server/portfolio-api/
  content_pipeline/
    __init__.py
    models.py            # ContentItem dataclass, SignalCard helpers, STATUS + PILLARS constants
    adapters/
      __init__.py
      base.py            # SourceAdapter Protocol, AdapterParseError
      xiaoyuzhou.py      # parse_episodes() (pure) + XiaoyuzhouAdapter (I/O)
    transcriber.py       # Transcriber (faster-whisper, lazy import, mock mode) + segments_to_text()
    distiller.py         # build_distill_input(), parse_signal_card(), Distiller
    deliverer.py         # render_new_notice(), render_signal_card(), Deliverer
    store.py             # MemoryStore (in-memory) + PgStore (psycopg2), schema init
    orchestrator.py      # discover(), process_item(), run_once()
    run.py               # cron entrypoint (argparse: --dry-run / --once)
    run.sh               # cron wrapper (mirrors automation/daily-briefing/run-and-send.sh)
    requirements-pipeline.txt   # faster-whisper (lazy; not needed for tests/app)
    README.md            # how it runs, env vars, cron registration
  tests/
    test_content_models.py
    test_content_adapter.py
    test_content_transcriber.py
    test_content_distiller.py
    test_content_deliverer.py
    test_content_store.py
    test_content_orchestrator.py   # holds the small component fakes inline

skills/
  vi-podcast-distill/
    SKILL.md             # guides hermes to emit the 6-field 信号卡 JSON
```

Conventions to follow (observed in the repo):
- HTTP via `urllib.request` with a 20s timeout (`market_data.py:_http_get`). No `requests`.
- Optional heavy libs (`faster-whisper`) imported **lazily** inside functions (like `yfinance`/`akshare`).
- LLM + Feishu via `subprocess.run(["hermes", ...])`; a `*_MODE` env gates a `mock` path for local dev (`app.py:run_hermes`, `REPORT_MODE`).
- Pure logic separated from I/O behind injectable seams; tests use in-memory fakes (`tests/conftest.py:FakeNotionClient`).
- PG via a `_db()` contextmanager + idempotent `CREATE TABLE IF NOT EXISTS` (`app.py:_db`, `_init_db`).

Run tests with the repo's existing venv (note: TDD Guard's project root is hardcoded to the main checkout, so in this worktree disable its reporter):

```
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -m pytest <path> -v -p no:tdd_guard
```

For brevity below, that interpreter is written as `PYTEST`. Set it once per shell:

```bash
PYTEST="/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -m pytest -p no:tdd_guard"
```

All commands run from `server/portfolio-api/` (the pytest rootdir; `pythonpath = ["."]` per `pyproject.toml`).

---

### Task 0: Package skeleton + dependency manifest

**Files:**
- Create: `server/portfolio-api/content_pipeline/__init__.py`
- Create: `server/portfolio-api/content_pipeline/adapters/__init__.py`
- Create: `server/portfolio-api/content_pipeline/requirements-pipeline.txt`

- [ ] **Step 1: Create the package files**

`content_pipeline/__init__.py`:
```python
"""Source-agnostic content signal pipeline (子系统 A 第一实现).

Detect new items from a SourceAdapter → notify (A) → transcribe + distill
free items into a 信号卡 → deliver (B). See docs/superpowers/specs/
2026-06-14-content-signal-pipeline-design.md.
"""
```

`content_pipeline/adapters/__init__.py`:
```python
"""Source adapters. The SourceAdapter interface is the pipeline's only
source-coupled seam ('架子'); add a new source = add a new adapter here."""
```

`content_pipeline/requirements-pipeline.txt`:
```
# Heavy, lazy-imported — only needed on the server that runs transcription.
# Not required to run the app or the unit tests (mock mode covers those).
faster-whisper>=1.0
```

- [ ] **Step 2: Verify the package imports**

Run: `PYTEST -q -p no:cacheprovider` then:
```bash
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -c "import content_pipeline; print('ok')"
```
Expected: prints `ok` (run from `server/portfolio-api/`).

- [ ] **Step 3: Commit**
```bash
git add content_pipeline/__init__.py content_pipeline/adapters/__init__.py content_pipeline/requirements-pipeline.txt
git commit -m "feat(pipeline): content_pipeline package skeleton + deps"
```

---

### Task 1: Models — ContentItem, status + pillar constants

**Files:**
- Create: `server/portfolio-api/content_pipeline/models.py`
- Test: `server/portfolio-api/tests/test_content_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_content_models.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.models'`

- [ ] **Step 3: Write minimal implementation**

`content_pipeline/models.py`:
```python
"""Pipeline data types + shared constants (no I/O)."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ContentItem:
    """A single source item, source-agnostic. media_url may be None for paid items."""
    source: str
    external_id: str
    title: str
    url: str
    published_at: str        # ISO 8601 string
    is_paid: bool = False
    media_url: str | None = None


class STATUS:
    NEW = "new"
    NOTIFIED = "notified"
    DOWNLOADING = "downloading"
    TRANSCRIBING = "transcribing"
    DISTILLED = "distilled"
    DELIVERED = "delivered"
    SKIPPED_PAID = "skipped_paid"
    ERROR = "error"


# Statuses from which an item still needs work on the next run.
RESUMABLE = (STATUS.NOTIFIED, STATUS.DOWNLOADING, STATUS.TRANSCRIBING, STATUS.DISTILLED)

# Signal-card pillar enum (the three lenses + 无).
PILLARS = ("第一性原理", "资金传导", "历史镜像", "无")

# Required keys in a valid 信号卡.
REQUIRED_CARD_KEYS = ("tldr", "non_consensus", "new_angle", "pillar", "caution", "worth_relisten")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_models.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/models.py tests/test_content_models.py
git commit -m "feat(pipeline): ContentItem model + status/pillar constants"
```

---

### Task 2: SourceAdapter interface + AdapterParseError

**Files:**
- Create: `server/portfolio-api/content_pipeline/adapters/base.py`

(No dedicated test — it's a Protocol + exception with no logic; it is exercised by Task 3's adapter and Task 9's orchestrator tests.)

- [ ] **Step 1: Write the interface**

`content_pipeline/adapters/base.py`:
```python
"""The pipeline's only source-coupled seam. A new content source = a new class
implementing SourceAdapter. Nothing downstream knows which source it is."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from content_pipeline.models import ContentItem


class AdapterParseError(Exception):
    """Raised when a source page can't be parsed (e.g. site structure changed).
    The orchestrator surfaces this so the operator gets a '适配器需修' alert —
    it must NOT be swallowed into a generic per-item error."""


class SourceAdapter(Protocol):
    source: str

    def list_items(self) -> list[ContentItem]:
        """Fetch the currently-visible items for this source (newest first)."""
        ...

    def fetch_media(self, item: ContentItem) -> Path:
        """Download the item's audio to a local file and return its path."""
        ...
```

- [ ] **Step 2: Verify it imports**
```bash
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -c "from content_pipeline.adapters.base import SourceAdapter, AdapterParseError; print('ok')"
```
Expected: prints `ok`

- [ ] **Step 3: Commit**
```bash
git add content_pipeline/adapters/base.py
git commit -m "feat(pipeline): SourceAdapter interface + AdapterParseError"
```

---

### Task 3: Xiaoyuzhou parser (pure) — `parse_episodes`

**Files:**
- Create: `server/portfolio-api/content_pipeline/adapters/xiaoyuzhou.py`
- Test: `server/portfolio-api/tests/test_content_adapter.py`

- [ ] **Step 1: Write the failing test**

`tests/test_content_adapter.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.adapters.xiaoyuzhou'`

- [ ] **Step 3: Write minimal implementation (parser only)**

`content_pipeline/adapters/xiaoyuzhou.py`:
```python
"""小宇宙 (xiaoyuzhoufm.com) adapter.

The podcast page is a Next.js app embedding one
<script id="__NEXT_DATA__">…</script> JSON blob. Episodes live at
props.pageProps.podcast.episodes[]. Verified against the live page 2026-06-14.
"""
from __future__ import annotations

import json
import re

from content_pipeline.adapters.base import AdapterParseError
from content_pipeline.models import ContentItem

SOURCE = "xiaoyuzhou"
PODCAST_URL = "https://www.xiaoyuzhoufm.com/podcast/{pid}"
EPISODE_URL = "https://www.xiaoyuzhoufm.com/episode/{eid}"
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def parse_episodes(html: str, pid: str) -> list[ContentItem]:
    """Parse a podcast page's HTML into ContentItems. Raises AdapterParseError
    if the page has no __NEXT_DATA__, bad JSON, or an unexpected shape."""
    m = _NEXT_DATA_RE.search(html or "")
    if not m:
        raise AdapterParseError("no __NEXT_DATA__ script found")
    try:
        data = json.loads(m.group(1))
        episodes = data["props"]["pageProps"]["podcast"]["episodes"]
    except (ValueError, KeyError, TypeError) as e:
        raise AdapterParseError(f"unexpected __NEXT_DATA__ shape: {e}") from e
    if not isinstance(episodes, list):
        raise AdapterParseError("episodes is not a list")

    items: list[ContentItem] = []
    for ep in episodes:
        eid = ep.get("eid")
        if not eid:
            continue
        items.append(ContentItem(
            source=SOURCE,
            external_id=eid,
            title=ep.get("title", ""),
            url=EPISODE_URL.format(eid=eid),
            published_at=ep.get("pubDate", ""),
            is_paid=(ep.get("payType") != "FREE"),
            media_url=(ep.get("enclosure") or {}).get("url"),
        ))
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_adapter.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/adapters/xiaoyuzhou.py tests/test_content_adapter.py
git commit -m "feat(pipeline): xiaoyuzhou __NEXT_DATA__ parser (pure)"
```

---

### Task 4: XiaoyuzhouAdapter I/O — `list_items` + `fetch_media`

**Files:**
- Modify: `server/portfolio-api/content_pipeline/adapters/xiaoyuzhou.py`
- Test: `server/portfolio-api/tests/test_content_adapter.py` (append)

- [ ] **Step 1: Write the failing test (append to test_content_adapter.py)**
```python
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
```

Add near the top of the test file (after `PID = ...`):
```python
from content_pipeline.adapters.xiaoyuzhou import PODCAST_URL
from content_pipeline.models import ContentItem
PODCAST_URL_FOR_TEST = PODCAST_URL.format(pid=PID)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_adapter.py -v`
Expected: FAIL — `ImportError: cannot import name 'XiaoyuzhouAdapter'`

- [ ] **Step 3: Write minimal implementation (append to xiaoyuzhou.py)**
```python
import tempfile
import urllib.request
from pathlib import Path

_HTTP_TIMEOUT = 20
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")


def _default_http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as r:
        return r.read()


class XiaoyuzhouAdapter:
    """SourceAdapter for 小宇宙. http_get is injectable for tests."""
    source = SOURCE

    def __init__(self, podcast_id: str, http_get=_default_http_get, tmp_dir=None):
        self.podcast_id = podcast_id
        self._get = http_get
        self._tmp_dir = Path(tmp_dir) if tmp_dir else Path(tempfile.gettempdir())

    def list_items(self) -> list[ContentItem]:
        html = self._get(PODCAST_URL.format(pid=self.podcast_id)).decode("utf-8", "replace")
        return parse_episodes(html, self.podcast_id)

    def fetch_media(self, item: ContentItem) -> Path:
        if not item.media_url:
            raise ValueError(f"item {item.external_id} has no media_url")
        data = self._get(item.media_url)
        out = self._tmp_dir / f"{item.source}_{item.external_id}.m4a"
        out.write_bytes(data)
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_adapter.py -v`
Expected: PASS (9 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/adapters/xiaoyuzhou.py tests/test_content_adapter.py
git commit -m "feat(pipeline): XiaoyuzhouAdapter list_items + fetch_media"
```

---

### Task 5: Transcriber (faster-whisper, lazy + mock mode)

**Files:**
- Create: `server/portfolio-api/content_pipeline/transcriber.py`
- Test: `server/portfolio-api/tests/test_content_transcriber.py`

- [ ] **Step 1: Write the failing test**

`tests/test_content_transcriber.py`:
```python
from content_pipeline.transcriber import segments_to_text, Transcriber


def test_segments_to_text_joins_with_timestamps():
    segs = [{"start": 0.0, "end": 2.0, "text": " 你好"}, {"start": 2.0, "end": 4.0, "text": "世界 "}]
    text, stamped = segments_to_text(segs)
    assert text == "你好世界"
    assert stamped[0]["start"] == 0.0
    assert stamped[0]["text"] == "你好"


def test_transcriber_mock_mode_returns_placeholder(tmp_path):
    f = tmp_path / "a.m4a"
    f.write_bytes(b"x")
    t = Transcriber(mode="mock")
    out = t.transcribe(f)
    assert "text" in out and "segments" in out
    assert out["text"]  # non-empty placeholder
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_transcriber.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.transcriber'`

- [ ] **Step 3: Write minimal implementation**

`content_pipeline/transcriber.py`:
```python
"""Audio → text via faster-whisper. Lazy import (heavy model) + a 'mock' mode
so local dev / tests never need the model. Set VI_WHISPER_MODE=mock to mock."""
from __future__ import annotations

import os
from pathlib import Path


def segments_to_text(segments) -> tuple[str, list[dict]]:
    """Join whisper segments into full text + a cleaned [{start,end,text}] list."""
    stamped = [{"start": s["start"], "end": s["end"], "text": s["text"].strip()}
               for s in segments]
    text = "".join(s["text"] for s in stamped)
    return text, stamped


class Transcriber:
    def __init__(self, mode: str | None = None, model_name: str = "large-v3"):
        self.mode = mode or os.environ.get("VI_WHISPER_MODE", "whisper")
        self.model_name = model_name

    def transcribe(self, audio_path) -> dict:
        if self.mode == "mock":
            return {"text": "（mock 转录占位文本）", "segments": [
                {"start": 0.0, "end": 1.0, "text": "（mock 转录占位文本）"}]}
        from faster_whisper import WhisperModel  # lazy: heavy
        model = WhisperModel(self.model_name, device="auto", compute_type="auto")
        segments, _info = model.transcribe(str(Path(audio_path)), language="zh")
        seg_dicts = [{"start": s.start, "end": s.end, "text": s.text} for s in segments]
        text, stamped = segments_to_text(seg_dicts)
        return {"text": text, "segments": stamped}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_transcriber.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/transcriber.py tests/test_content_transcriber.py
git commit -m "feat(pipeline): Transcriber (faster-whisper lazy + mock mode)"
```

---

### Task 6: Distiller — prompt build, card parse, hermes-skill call

**Files:**
- Create: `server/portfolio-api/content_pipeline/distiller.py`
- Test: `server/portfolio-api/tests/test_content_distiller.py`

- [ ] **Step 1: Write the failing test**

`tests/test_content_distiller.py`:
```python
import json
import pytest

from content_pipeline.models import ContentItem
from content_pipeline.distiller import build_distill_input, parse_signal_card, Distiller


def _item():
    return ContentItem(source="xiaoyuzhou", external_id="e1", title="Ep 9 | 测试",
                       url="u", published_at="p", is_paid=False, media_url="m")


def _valid_card():
    return {"tldr": "主旨", "non_consensus": "他认为X而共识Y", "new_angle": "迁移角度",
            "pillar": "资金传导", "caution": "他重crypto，注意利益相关",
            "worth_relisten": {"yes": True, "timestamps": ["12:30 关于X"]}}


def test_build_input_includes_title_and_transcript_and_pillars():
    s = build_distill_input(_item(), "这是转录全文。")
    assert "Ep 9 | 测试" in s
    assert "这是转录全文。" in s
    assert "第一性原理" in s and "资金传导" in s and "历史镜像" in s


def test_parse_signal_card_accepts_plain_json():
    card = parse_signal_card(json.dumps(_valid_card(), ensure_ascii=False))
    assert card["pillar"] == "资金传导"
    assert card["worth_relisten"]["yes"] is True


def test_parse_signal_card_extracts_from_fenced_block():
    raw = "好的，结果如下：\n```json\n" + json.dumps(_valid_card(), ensure_ascii=False) + "\n```\n"
    card = parse_signal_card(raw)
    assert card["tldr"] == "主旨"


def test_parse_signal_card_rejects_missing_key():
    bad = _valid_card(); del bad["caution"]
    with pytest.raises(ValueError):
        parse_signal_card(json.dumps(bad, ensure_ascii=False))


def test_parse_signal_card_rejects_bad_pillar():
    bad = _valid_card(); bad["pillar"] = "玄学"
    with pytest.raises(ValueError):
        parse_signal_card(json.dumps(bad, ensure_ascii=False))


def test_parse_signal_card_rejects_non_json():
    with pytest.raises(ValueError):
        parse_signal_card("我没有返回 json")


def test_distill_calls_runner_and_parses():
    captured = {}

    def fake_runner(prompt):
        captured["prompt"] = prompt
        return json.dumps(_valid_card(), ensure_ascii=False)

    card = Distiller(runner=fake_runner).distill(_item(), "转录")
    assert "转录" in captured["prompt"]
    assert card["pillar"] == "资金传导"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_distiller.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.distiller'`

- [ ] **Step 3: Write minimal implementation**

`content_pipeline/distiller.py`:
```python
"""Transcript → 信号卡 (structured JSON) via the hermes skill vi-podcast-distill.

build_distill_input / parse_signal_card are pure (unit-tested). distill() wires a
runner (subprocess by default) so tests inject a fake. The card schema is
pre-aligned to capture_note for the future Notion (C) hookup."""
from __future__ import annotations

import json
import os
import re
import subprocess

from content_pipeline.models import ContentItem, PILLARS, REQUIRED_CARD_KEYS

_PROFILE = os.environ.get("VI_PIPELINE_PROFILE", "app-lucas")
_SKILL = "vi-podcast-distill"
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.S)
_JSON_OBJ_RE = re.compile(r"\{.*\}", re.S)


def build_distill_input(item: ContentItem, transcript: str) -> str:
    """The instruction + transcript handed to the vi-podcast-distill skill."""
    return (
        f"播客《非共识的20分钟》单集：{item.title}\n"
        f"链接：{item.url}\n\n"
        "请按 vi-podcast-distill 技能，把下面的转录蒸馏成一张『信号卡』，"
        "只输出一个 JSON 对象（可包在 ```json 代码块里），字段：\n"
        "- tldr：一句话主旨\n"
        "- non_consensus：他和市场共识具体哪里不一样\n"
        "- new_angle：可迁移到价值投资框架的角度\n"
        f"- pillar：命中的支柱，取值之一 {list(PILLARS)}\n"
        "- caution：他可能错在哪 / 利益相关 / 他重 crypto-宏观的倾向提醒\n"
        '- worth_relisten：{"yes": bool, "timestamps": ["mm:ss 关于…"]}\n'
        "绝不编造内容；转录没讲到的不要硬填。\n\n"
        f"【转录全文】\n{transcript}\n"
    )


def parse_signal_card(raw: str) -> dict:
    """Extract + validate a 信号卡 from hermes output. Raises ValueError if the
    text isn't valid JSON, is missing a required key, or has a bad pillar."""
    text = (raw or "").strip()
    candidate = None
    m = _JSON_FENCE_RE.search(text) or _JSON_OBJ_RE.search(text)
    if m:
        candidate = m.group(1) if m.re is _JSON_FENCE_RE else m.group(0)
    if candidate is None:
        raise ValueError("no JSON object found in distiller output")
    try:
        card = json.loads(candidate)
    except ValueError as e:
        raise ValueError(f"distiller output is not valid JSON: {e}") from e
    if not isinstance(card, dict):
        raise ValueError("distiller output is not a JSON object")
    missing = [k for k in REQUIRED_CARD_KEYS if k not in card]
    if missing:
        raise ValueError(f"signal card missing keys: {missing}")
    if card["pillar"] not in PILLARS:
        raise ValueError(f"bad pillar: {card['pillar']!r}")
    wr = card.get("worth_relisten")
    if not isinstance(wr, dict) or "yes" not in wr:
        raise ValueError("worth_relisten must be an object with a 'yes' field")
    return card


def _hermes_skill_runner(prompt: str) -> str:
    r = subprocess.run(
        ["hermes", "-p", _PROFILE, "--skills", _SKILL, "-z", prompt],
        capture_output=True, text=True, timeout=300)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError((r.stderr or "").strip()[-300:] or "hermes 返回空内容")
    return out


class Distiller:
    def __init__(self, runner=_hermes_skill_runner):
        self._runner = runner

    def distill(self, item: ContentItem, transcript: str) -> dict:
        raw = self._runner(build_distill_input(item, transcript))
        return parse_signal_card(raw)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_distiller.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/distiller.py tests/test_content_distiller.py
git commit -m "feat(pipeline): Distiller — prompt build + signal-card parse/validate"
```

---

### Task 7: Deliverer — render A/B + hermes send

**Files:**
- Create: `server/portfolio-api/content_pipeline/deliverer.py`
- Test: `server/portfolio-api/tests/test_content_deliverer.py`

- [ ] **Step 1: Write the failing test**

`tests/test_content_deliverer.py`:
```python
from content_pipeline.models import ContentItem
from content_pipeline.deliverer import render_new_notice, render_signal_card, Deliverer


def _item(paid=False):
    return ContentItem(source="xiaoyuzhou", external_id="e1", title="Ep 9 | 测试",
                       url="https://x/episode/e1", published_at="p",
                       is_paid=paid, media_url="m")


def _card():
    return {"tldr": "主旨", "non_consensus": "他X共识Y", "new_angle": "迁移角度",
            "pillar": "资金传导", "caution": "注意利益相关",
            "worth_relisten": {"yes": True, "timestamps": ["12:30 关于X"]}}


def test_render_new_notice_has_title_and_link():
    s = render_new_notice(_item())
    assert "Ep 9 | 测试" in s
    assert "https://x/episode/e1" in s


def test_render_new_notice_paid_marks_paid():
    s = render_new_notice(_item(paid=True))
    assert "付费" in s


def test_render_signal_card_has_all_fields():
    s = render_signal_card(_item(), _card())
    for piece in ["主旨", "他X共识Y", "迁移角度", "资金传导", "注意利益相关", "12:30"]:
        assert piece in s


def test_deliverer_send_new_notice_calls_runner():
    sent = []
    d = Deliverer(runner=lambda text, subject: sent.append((subject, text)))
    d.send_new_notice(_item())
    assert len(sent) == 1
    assert "Ep 9 | 测试" in sent[0][1]


def test_deliverer_send_signal_card_calls_runner():
    sent = []
    d = Deliverer(runner=lambda text, subject: sent.append((subject, text)))
    d.send_signal_card(_item(), _card())
    assert "资金传导" in sent[0][1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_deliverer.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.deliverer'`

- [ ] **Step 3: Write minimal implementation**

`content_pipeline/deliverer.py`:
```python
"""Render + push pipeline messages to Feishu via `hermes send`. render_* are
pure (unit-tested); Deliverer wraps the subprocess with an injectable runner."""
from __future__ import annotations

import os
import subprocess

from content_pipeline.models import ContentItem

_TARGET = os.environ.get("VI_PIPELINE_FEISHU_TARGET", "feishu")


def render_new_notice(item: ContentItem) -> str:
    paid = "（付费集，管道够不着，需自听）" if item.is_paid else ""
    return f"🎙️ 新集{paid}：{item.title}\n{item.url}"


def render_signal_card(item: ContentItem, card: dict) -> str:
    wr = card.get("worth_relisten") or {}
    relisten = "值得回听" if wr.get("yes") else "可跳过"
    stamps = "；".join(wr.get("timestamps") or [])
    lines = [
        f"🧭 信号卡 · {item.title}",
        "",
        f"主旨：{card.get('tldr','')}",
        f"非共识：{card.get('non_consensus','')}",
        f"新角度：{card.get('new_angle','')}",
        f"支柱：{card.get('pillar','')}",
        f"⚠️ 警惕：{card.get('caution','')}",
        f"回听：{relisten}" + (f"（{stamps}）" if stamps else ""),
        "",
        f"原集：{item.url}",
    ]
    return "\n".join(lines)


def _hermes_send(text: str, subject: str) -> None:
    r = subprocess.run(["hermes", "send", "--to", _TARGET, "--subject", subject],
                       input=text, capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise RuntimeError("hermes send 失败：" + (r.stderr.strip()[-200:] or "unknown"))


class Deliverer:
    def __init__(self, runner=_hermes_send):
        self._send = runner

    def send_new_notice(self, item: ContentItem) -> None:
        self._send(render_new_notice(item), "🎙️ 非共识的20分钟 · 新集")

    def send_signal_card(self, item: ContentItem, card: dict) -> None:
        self._send(render_signal_card(item, card), "🧭 信号卡 · 非共识的20分钟")

    def send_alert(self, text: str) -> None:
        self._send(text, "⚠️ 内容管道告警")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_deliverer.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/deliverer.py tests/test_content_deliverer.py
git commit -m "feat(pipeline): Deliverer — render A/B + hermes send"
```

---

### Task 8: Store — MemoryStore + PgStore

**Files:**
- Create: `server/portfolio-api/content_pipeline/store.py`
- Test: `server/portfolio-api/tests/test_content_store.py`

The orchestrator depends on a small `Store` surface: `init_schema()`, `seen_ids(source)`, `add(item)`, `get(source, eid)`, `set_status(source, eid, status)`, `save_transcript(...)`, `save_card(...)`, `mark_error(...) -> int`, `resumable(source, max_retries)`. We ship **two** implementations of this surface in the production module (`content_pipeline/store.py`): `MemoryStore` (in-memory — used by unit tests and `run.py --dry-run`) and `PgStore` (PostgreSQL). Keeping `MemoryStore` in the package (not under `tests/`) avoids production code importing from the test tree. We TDD `MemoryStore`; `PgStore` mirrors it method-for-method and is verified by an optional smoke test (skipped when no DB).

- [ ] **Step 1: Write the failing test for MemoryStore**

`tests/test_content_store.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'MemoryStore'` (module/name missing)

- [ ] **Step 3: Write store.py with MemoryStore (minimal to pass)**

`content_pipeline/store.py`:
```python
"""Store: dedup + status state machine + transcript/card archive.

Two implementations of the same surface:
  - MemoryStore: in-memory (unit tests + `run.py --dry-run`).
  - PgStore: PostgreSQL, schema created idempotently (mirrors app.py's _init_db).
They mirror each other method-for-method."""
from __future__ import annotations

import json
import os
from contextlib import contextmanager

from content_pipeline.models import ContentItem, STATUS, RESUMABLE


def _row(item: ContentItem) -> dict:
    return {"source": item.source, "external_id": item.external_id, "title": item.title,
            "url": item.url, "published_at": item.published_at, "is_paid": item.is_paid,
            "media_url": item.media_url, "status": STATUS.NEW, "transcript": None,
            "signal_card": None, "error": None, "error_count": 0}


def _to_item(row: dict) -> ContentItem:
    pub = row.get("published_at")
    return ContentItem(source=row["source"], external_id=row["external_id"],
                       title=row["title"], url=row["url"],
                       published_at=pub.isoformat() if hasattr(pub, "isoformat") else (pub or ""),
                       is_paid=row["is_paid"], media_url=row["media_url"])


class MemoryStore:
    def __init__(self):
        self.rows: dict[tuple, dict] = {}
        self.schema_inited = False

    def init_schema(self):
        self.schema_inited = True

    def seen_ids(self, source):
        return {eid for (src, eid) in self.rows if src == source}

    def add(self, item: ContentItem):
        self.rows.setdefault((item.source, item.external_id), _row(item))

    def get(self, source, eid):
        return self.rows.get((source, eid))

    def set_status(self, source, eid, status):
        self.rows[(source, eid)]["status"] = status

    def save_transcript(self, source, eid, text):
        self.rows[(source, eid)]["transcript"] = text

    def save_card(self, source, eid, card):
        self.rows[(source, eid)]["signal_card"] = card

    def mark_error(self, source, eid, msg) -> int:
        r = self.rows[(source, eid)]
        r["status"] = STATUS.ERROR
        r["error"] = msg
        r["error_count"] += 1
        return r["error_count"]

    def resumable(self, source, max_retries=3):
        out = []
        for (src, eid), r in self.rows.items():
            if src != source:
                continue
            if r["status"] in RESUMABLE or (r["status"] == STATUS.ERROR and r["error_count"] < max_retries):
                out.append(_to_item(r))
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_store.py -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Append PgStore to store.py (mirrors MemoryStore against PostgreSQL)**

Append to `content_pipeline/store.py`:
```python
# --------------------------------------------------------------------------- #
# PgStore — PostgreSQL implementation of the same surface
# --------------------------------------------------------------------------- #
import psycopg2          # noqa: E402
import psycopg2.extras   # noqa: E402

DB_URL = os.environ.get("VI_DATABASE_URL", "")
RDC = psycopg2.extras.RealDictCursor


@contextmanager
def _db():
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


class PgStore:
    def init_schema(self):
        with _db() as c, c.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS content_items (
                    source       TEXT NOT NULL,
                    external_id  TEXT NOT NULL,
                    title        TEXT,
                    url          TEXT,
                    published_at TIMESTAMPTZ,
                    is_paid      BOOLEAN NOT NULL DEFAULT FALSE,
                    media_url    TEXT,
                    status       TEXT NOT NULL DEFAULT 'new',
                    transcript   TEXT,
                    signal_card  JSONB,
                    error        TEXT,
                    error_count  INTEGER NOT NULL DEFAULT 0,
                    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
                    PRIMARY KEY (source, external_id)
                );
                CREATE INDEX IF NOT EXISTS content_items_status_idx
                    ON content_items(source, status);
            """)

    def seen_ids(self, source) -> set:
        with _db() as c, c.cursor() as cur:
            cur.execute("SELECT external_id FROM content_items WHERE source=%s", (source,))
            return {r[0] for r in cur.fetchall()}

    def add(self, item: ContentItem):
        with _db() as c, c.cursor() as cur:
            cur.execute("""
                INSERT INTO content_items
                    (source, external_id, title, url, published_at, is_paid, media_url, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,'new')
                ON CONFLICT (source, external_id) DO NOTHING
            """, (item.source, item.external_id, item.title, item.url,
                  item.published_at or None, item.is_paid, item.media_url))

    def get(self, source, eid):
        with _db() as c, c.cursor(cursor_factory=RDC) as cur:
            cur.execute("SELECT * FROM content_items WHERE source=%s AND external_id=%s",
                        (source, eid))
            r = cur.fetchone()
            return dict(r) if r else None

    def set_status(self, source, eid, status):
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE content_items SET status=%s, updated_at=now() "
                        "WHERE source=%s AND external_id=%s", (status, source, eid))

    def save_transcript(self, source, eid, text):
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE content_items SET transcript=%s, updated_at=now() "
                        "WHERE source=%s AND external_id=%s", (text, source, eid))

    def save_card(self, source, eid, card):
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE content_items SET signal_card=%s, updated_at=now() "
                        "WHERE source=%s AND external_id=%s",
                        (json.dumps(card, ensure_ascii=False), source, eid))

    def mark_error(self, source, eid, msg) -> int:
        with _db() as c, c.cursor() as cur:
            cur.execute("""UPDATE content_items
                SET status='error', error=%s, error_count=error_count+1, updated_at=now()
                WHERE source=%s AND external_id=%s
                RETURNING error_count""", (str(msg)[:500], source, eid))
            return cur.fetchone()[0]

    def resumable(self, source, max_retries=3):
        with _db() as c, c.cursor(cursor_factory=RDC) as cur:
            cur.execute("""SELECT * FROM content_items
                WHERE source=%s AND (status = ANY(%s) OR (status='error' AND error_count < %s))
                ORDER BY published_at NULLS LAST""",
                (source, list(RESUMABLE), max_retries))
            return [_to_item(dict(r)) for r in cur.fetchall()]
```

- [ ] **Step 6: Append an optional PgStore smoke test (skipped without DB)**

Append to `tests/test_content_store.py`:
```python
@pytest.mark.skipif(not os.environ.get("VI_DATABASE_URL"), reason="no VI_DATABASE_URL")
def test_pgstore_roundtrip():
    from content_pipeline.store import PgStore
    s = PgStore(); s.init_schema()
    s.add(_item("smoke-1"))
    assert "smoke-1" in s.seen_ids("xiaoyuzhou")
    s.set_status("xiaoyuzhou", "smoke-1", STATUS.NOTIFIED)
    assert any(i.external_id == "smoke-1" for i in s.resumable("xiaoyuzhou"))
```

- [ ] **Step 7: Run tests to verify they pass (smoke test skips locally)**

Run: `PYTEST tests/test_content_store.py -v`
Expected: PASS (6 passed, 1 skipped)

- [ ] **Step 8: Commit**
```bash
git add content_pipeline/store.py tests/test_content_store.py
git commit -m "feat(pipeline): Store — MemoryStore + PgStore (dedup + state machine)"
```

---

### Task 9: Orchestrator — discover, process_item, run_once

**Files:**
- Create: `server/portfolio-api/content_pipeline/orchestrator.py`
- Test: `server/portfolio-api/tests/test_content_orchestrator.py`

The four component seams (adapter/transcriber/distiller/deliverer) are faked inline in this test file — they're only used here, so no shared test module is needed. The store seam reuses the production `MemoryStore` from Task 8.

- [ ] **Step 1: Write the failing test (with inline component fakes)**

`tests/test_content_orchestrator.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTEST tests/test_content_orchestrator.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'content_pipeline.orchestrator'`

- [ ] **Step 3: Write minimal implementation**

`content_pipeline/orchestrator.py`:
```python
"""Ties the pipeline together: discover new items (send A, skip paid), then
advance each free item through download → transcribe → distill → deliver B.
Idempotent and resumable via the Store state machine. Pure-ish: all I/O is
behind the injected adapter/store/transcriber/distiller/deliverer seams."""
from __future__ import annotations

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
    """One full poll cycle. Lets AdapterParseError propagate (caller alerts)."""
    store.init_schema()
    discover(adapter, store, deliverer)
    for it in store.resumable(adapter.source, max_retries):
        process_item(adapter, it, store, transcriber, distiller, deliverer, max_retries)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTEST tests/test_content_orchestrator.py -v`
Expected: PASS (7 passed)

- [ ] **Step 5: Run the whole pipeline suite**

Run: `PYTEST tests/test_content_*.py -v`
Expected: all PASS (smoke test skipped)

- [ ] **Step 6: Commit**
```bash
git add content_pipeline/orchestrator.py tests/test_content_orchestrator.py
git commit -m "feat(pipeline): orchestrator — discover + process_item + run_once (idempotent, resumable)"
```

---

### Task 10: `vi-podcast-distill` skill

**Files:**
- Create: `skills/vi-podcast-distill/SKILL.md`

(No automated test — it's an instruction doc, mirroring `skills/vi-capture-note/SKILL.md`. The distiller's `parse_signal_card` already enforces the contract.)

- [ ] **Step 1: Write the skill**

`skills/vi-podcast-distill/SKILL.md`:
```markdown
---
name: vi-podcast-distill
description: Distill a podcast transcript into a structured 信号卡 JSON (非共识点 + 可迁移角度 + 该警惕什么) for the content signal pipeline.
---

# 播客信号蒸馏技能

把一段播客转录蒸馏成一张**信号卡**——不是摘要,而是逼出"反共识 + 可迁移到价值投资框架的角度 + 该存疑的地方"。只输出**一个 JSON 对象**(可包在 ```json 代码块里),不要任何其他文字。

## 输出字段(全部必填)
- `tldr`:一句话主旨。
- `non_consensus`:他和市场共识具体哪里不一样(没有就写"本集未给出明显非共识点")。
- `new_angle`:能迁移到价值投资分析的角度。
- `pillar`:命中的支柱,取值之一:`第一性原理` / `资金传导` / `历史镜像` / `无`。
- `caution`:他可能错在哪 / 利益相关 / 他重 crypto-宏观的倾向提醒。
- `worth_relisten`:`{"yes": true|false, "timestamps": ["mm:ss 关于…"]}`——是否值得回听原集 + 关键时间点。

## 判据
- **non_consensus**:市场共识默认是什么?他在哪一点上明确反对/给出不同概率?抓"他认为 X,而价格/共识隐含 Y"。
- **pillar**:第一性原理=把生意/资产拆到本质;资金传导=钱怎么流(内部现金链 / 宏观利率流动性 / 产业链议价);历史镜像=放进历史周期与类比看。对不上就 `无`。
- **caution**:他是持牌基金管理人且**重 crypto-宏观**,天然有 book/方向上的利益相关——永远点出这点 + 他这集论断里最可能错的一环。

## 硬约束
- **绝不编造**:转录没讲到的不要硬填;某字段无内容就如实写"本集未涉及"。
- 只输出 JSON,不要前后缀解释。
```

- [ ] **Step 2: Validate it parses as a skill (frontmatter + body present)**
```bash
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -c "
import pathlib, re
t = pathlib.Path('../../skills/vi-podcast-distill/SKILL.md').read_text('utf-8')
assert t.startswith('---') and 'name: vi-podcast-distill' in t and 'worth_relisten' in t
print('skill ok')"
```
Run from `server/portfolio-api/`. Expected: prints `skill ok`

- [ ] **Step 3: Commit**
```bash
git add ../../skills/vi-podcast-distill/SKILL.md
git commit -m "feat(pipeline): vi-podcast-distill skill (信号卡 JSON contract)"
```

---

### Task 11: Cron entrypoint `run.py` + wrapper `run.sh`

**Files:**
- Create: `server/portfolio-api/content_pipeline/run.py`
- Create: `server/portfolio-api/content_pipeline/run.sh`

- [ ] **Step 1: Write the entrypoint**

`content_pipeline/run.py`:
```python
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
import os
import sys

from content_pipeline.adapters.base import AdapterParseError
from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.deliverer import Deliverer
from content_pipeline.distiller import Distiller
from content_pipeline.transcriber import Transcriber
from content_pipeline import orchestrator

PODCAST_ID = os.environ.get("VI_PIPELINE_PODCAST_ID", "6978a31df828d4e9f2787d3d")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Content signal pipeline — one poll cycle")
    parser.add_argument("--dry-run", action="store_true",
                        help="Mock whisper+hermes, in-memory store, print actions only")
    args = parser.parse_args(argv)

    adapter = XiaoyuzhouAdapter(PODCAST_ID)

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
        transcriber = Transcriber()
        distiller = Distiller()
        deliverer = Deliverer()

    try:
        orchestrator.run_once(adapter, store, transcriber, distiller, deliverer)
    except AdapterParseError as e:
        msg = f"⚠️ 适配器需修（{adapter.source}）：{e}"
        print(msg, file=sys.stderr)
        try:
            deliverer.send_alert(msg)
        except Exception:  # noqa: BLE001
            pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

`content_pipeline/run.sh`:
```bash
#!/usr/bin/env bash
# Run the content signal pipeline once and deliver to Feishu via hermes.
#
# Run ON THE SERVER (hermes + PostgreSQL + faster-whisper installed). Schedule:
#
#   • system cron (crontab -e) — 08:00 北京时间.
#     If the server clock is UTC, that is 00:00 UTC:
#       0 0 * * *  /path/to/run.sh >> /var/log/content-pipeline.log 2>&1
#     If TZ=Asia/Shanghai:
#       0 8 * * *  /path/to/run.sh >> /var/log/content-pipeline.log 2>&1
#
#   • or hermes cron:
#       hermes cron create --name content-pipeline --schedule "0 0 * * *" \
#         --command "/path/to/run.sh"
set -euo pipefail
cd "$(dirname "$0")/.."          # server/portfolio-api (pythonpath root)
exec python3 -m content_pipeline.run "$@"
```

- [ ] **Step 2: Make the wrapper executable**
```bash
chmod +x content_pipeline/run.sh
```

- [ ] **Step 3: Smoke-test the dry run (mock everything; hits the live podcast page over the network)**

Run from `server/portfolio-api/`:
```bash
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -m content_pipeline.run --dry-run
```
Expected: prints `[A] …` lines for each currently-listed episode (paid ones tagged `PAID`), and `[B] …` lines for free ones. No exceptions. (If the network is blocked in your environment, this step is expected to fail at the HTTP fetch — note it and verify on the server instead.)

- [ ] **Step 4: Commit**
```bash
git add content_pipeline/run.py content_pipeline/run.sh
git commit -m "feat(pipeline): cron entrypoint run.py + run.sh wrapper"
```

---

### Task 12: README + resolve spec's deferred items

**Files:**
- Create: `server/portfolio-api/content_pipeline/README.md`
- Modify: `docs/superpowers/specs/2026-06-14-content-signal-pipeline-design.md`

- [ ] **Step 1: Write the README**

`content_pipeline/README.md`:
```markdown
# Content Signal Pipeline (子系统 A 第一实现)

Daily: detect new 小宇宙 episodes → Feishu notice (A) → transcribe + distill free
episodes into a 信号卡 (B). Source-agnostic behind `adapters/SourceAdapter`.

## Run
```
# one cycle (server: needs hermes + PostgreSQL + faster-whisper)
python -m content_pipeline.run
# dry run (mock whisper+hermes, in-memory store, prints actions)
python -m content_pipeline.run --dry-run
```

## Schedule
08:00 北京时间 daily. See `run.sh` header (system cron `0 0 * * *` if server is UTC,
or `0 8 * * *` with `TZ=Asia/Shanghai`; or `hermes cron`).

## Env vars
| var | default | meaning |
|---|---|---|
| `VI_DATABASE_URL` | — | PostgreSQL DSN (same as the app) |
| `VI_PIPELINE_PODCAST_ID` | `6978a31df828d4e9f2787d3d` | 小宇宙 pid to poll |
| `VI_WHISPER_MODE` | `whisper` | `mock` to skip the model |
| `VI_PIPELINE_PROFILE` | `app-lucas` | hermes profile for the distill skill |
| `VI_PIPELINE_FEISHU_TARGET` | `feishu` | `hermes send --to` target |

## Install transcription dep (server only)
```
pip install -r content_pipeline/requirements-pipeline.txt
```

## Add a new source
Implement `adapters/base.SourceAdapter` (`list_items` + `fetch_media`) in a new
module; nothing else changes. The pipeline is source-agnostic from there on.

## Future: Notion (C)
The 信号卡 schema (`models.REQUIRED_CARD_KEYS`) is pre-aligned to the
`capture_note` contract (情境=播客). Hook the delivered card into the
knowledge-precipitation flywheel to close 子系统 A → B.
```

- [ ] **Step 2: Resolve the spec's "留到实现阶段研究的细节" section**

In `docs/superpowers/specs/2026-06-14-content-signal-pipeline-design.md`, replace the bullet:
```
- 小宇宙 `__NEXT_DATA__` 里 episode 对象的确切字段路径(付费标记 / 音频 URL 的 key 名)——抓一份真实样本确认。
```
with:
```
- ✅ 已确认(2026-06-14 实测):episodes 在 `props.pageProps.podcast.episodes[]`;字段 `eid`/`title`/`pubDate`/`duration`/`payType`(`FREE` vs `PAY_EPISODE*`)/`enclosure.url`。仅嵌入最近 ~15 集(日轮询足够)。
- 备注:episode 对象另有 `transcript`/`transcriptMediaId` 字段——若官方已提供转录,未来可作为跳过 whisper 的捷径(本期不依赖)。
```

- [ ] **Step 3: Run the full suite one more time**

Run: `PYTEST -q -p no:cacheprovider`
Expected: original 30 tests + all new pipeline tests PASS (1 skipped).

- [ ] **Step 4: Commit**
```bash
git add content_pipeline/README.md docs/superpowers/specs/2026-06-14-content-signal-pipeline-design.md
git commit -m "docs(pipeline): README + resolve spec deferred items (verified __NEXT_DATA__ shape)"
```

---

## Definition of Done (maps to spec acceptance criteria)

1. ✅ Free new episode → A notice then B 信号卡 — `test_free_episode_happy_path_reaches_delivered`.
2. ✅ Paid episode → A only, no transcription — `test_paid_episode_only_notifies_and_skips`.
3. ✅ Dedup, idempotent — `test_dedup_skips_already_seen` + `PRIMARY KEY (source, external_id)` + `ON CONFLICT DO NOTHING`.
4. ✅ Failure → error + retry; transcript not wasted — `test_distill_failure_marks_error_but_keeps_transcript`, `test_retry_resumes_from_distill_without_retranscribing`.
5. ✅ Transcript archived, not pushed — `save_transcript` to PG; only `send_signal_card` pushes.
6. ✅ New source = new adapter only — `SourceAdapter` Protocol; orchestrator/store/transcriber/distiller/deliverer are source-agnostic.
7. ✅ Adapter parse failure → propagates → operator alert, pipeline not crashed mid-other-work — `test_adapter_parse_error_propagates` + `run.py` catches → `send_alert`.

Plus: max-retry alert (`test_max_retries_sends_alert_and_stops`), daily 08:00 北京时间 schedule (`run.sh`).
```
