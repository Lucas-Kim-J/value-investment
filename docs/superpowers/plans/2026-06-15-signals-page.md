# 信号 Hub Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A source-agnostic `📡 信号` hub page in the React app that browses the pipeline's signal cards — v1 wires the 播客/小宇宙 栏 (cover-art cards → expand to 6 fields + 原集链接 + on-demand transcript), with placeholder tabs for future sources.

**Architecture:** Three layers. (1) **Pipeline**: add `image_url` + `show_title` to `ContentItem`/`content_items` so the page has cover art + show name. (2) **Backend**: two read-only Flask endpoints over `content_items` (`signal_card IS NOT NULL`), with a pure row→dict shaper that's unit-tested (endpoints stay thin, matching the repo's habit of testing helpers not live queries). (3) **Frontend**: a new lazy page `Signals.tsx` + route + nav item + types, styled with existing design tokens, the 小宇宙 logo bundled as a static asset.

**Tech Stack:** Python (psycopg2, Flask) · faster-whisper pipeline (existing) · React 18 + TypeScript + Vite + react-router · Vitest + Testing Library · pytest.

---

## Reference: existing patterns (follow these)

- **Pipeline** (`server/portfolio-api/content_pipeline/`): `ContentItem` dataclass in `models.py`; `parse_episodes(html, pid)` in `adapters/xiaoyuzhou.py` reads `data["props"]["pageProps"]["podcast"]["episodes"]`; `MemoryStore`/`PgStore` in `store.py` share `_row`/`_to_item`.
- **`__NEXT_DATA__` podcast object** (verified 2026-06-14): `podcast.title` = show name; `podcast.image.middlePicUrl` = cover art URL. Episodes have no own image (reuse show cover).
- **Backend** (`app.py`): `_db()` contextmanager + `RDC = psycopg2.extras.RealDictCursor`; `_current_user()` returns username or None; routes like `@app.get("/api/canon")`. `import app` works without a DB (the `_init_db()` call is wrapped in try/except). psycopg2 returns JSONB columns as Python dicts.
- **Frontend page** (`web/src/pages/Canon.tsx`): default-export component; `useMe()` (undefined=loading / null=guest / string=user); `apiGet<{items:T[]}>("/api/...")` in `useEffect`; renders `.app-head` + cards using design tokens from `web/src/styles/global.css`.
- **Frontend test** (`web/src/shell/Markdown.test.tsx`): Vitest + `@testing-library/react` `render`/`screen`. Setup in `web/src/test/setup.ts`.
- **Types**: `web/src/lib/types.ts`. **API client**: `web/src/lib/api.ts` (`apiGet`). **Nav**: `web/src/app/Nav.tsx` (`ITEMS` array). **Routes**: `web/src/App.tsx` (lazy).

## Test commands

**Backend** (run from `server/portfolio-api/`):
```
PYTEST="/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -m pytest -p no:tdd_guard"
```
**Frontend** (run from `web/`; first task does `npm install`):
```
npx vitest run <file> --reporter=default     # single file, default reporter avoids the worktree tdd-guard root issue
```

All paths below are under the worktree:
`/Users/Zhuanz/Documents/code/value-investment/.claude/worktrees/content-signal-pipeline`
Confirm branch `feat/signals-frontend` (`git branch --show-current`) before committing; never switch branches.

---

### Task 1: ContentItem — add `image_url` + `show_title`

**Files:**
- Modify: `server/portfolio-api/content_pipeline/models.py`
- Test: `server/portfolio-api/tests/test_content_models.py`

- [ ] **Step 1: Write the failing test (append to test_content_models.py)**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_content_models.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'image_url'`

- [ ] **Step 3: Add the fields**

In `models.py`, change the `ContentItem` dataclass body to add two trailing optional fields:
```python
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
    image_url: str | None = None     # cover art (podcast-level, same for all episodes)
    show_title: str | None = None    # e.g. 非共识的20分钟
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/test_content_models.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/models.py tests/test_content_models.py
git commit -m "feat(signals): ContentItem carries image_url + show_title"
```

---

### Task 2: `parse_episodes` captures cover art + show title

**Files:**
- Modify: `server/portfolio-api/content_pipeline/adapters/xiaoyuzhou.py`
- Test: `server/portfolio-api/tests/test_content_adapter.py`

- [ ] **Step 1: Write the failing test (append to test_content_adapter.py)**
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_content_adapter.py -v`
Expected: FAIL — `AssertionError` (show_title/image_url are None; not yet captured)

- [ ] **Step 3: Capture the fields in `parse_episodes`**

In `xiaoyuzhou.py`, inside `parse_episodes`, after `episodes` is resolved and validated as a list, add the podcast-level lookups, then pass them to each `ContentItem`:
```python
    if not isinstance(episodes, list):
        raise AdapterParseError("episodes is not a list")

    podcast = data["props"]["pageProps"]["podcast"]
    show_title = podcast.get("title")
    image_url = (podcast.get("image") or {}).get("middlePicUrl")

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
            image_url=image_url,
            show_title=show_title,
        ))
    return items
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/test_content_adapter.py -v`
Expected: PASS (all, incl. the pre-existing parse tests)

- [ ] **Step 5: Commit**
```bash
git add content_pipeline/adapters/xiaoyuzhou.py tests/test_content_adapter.py
git commit -m "feat(signals): xiaoyuzhou parser captures cover art + show title"
```

---

### Task 3: Store persists `image_url` + `show_title`

**Files:**
- Modify: `server/portfolio-api/content_pipeline/store.py`
- Test: `server/portfolio-api/tests/test_content_store.py`

- [ ] **Step 1: Write the failing test (append to test_content_store.py)**
```python
def test_memorystore_persists_image_and_show_title():
    s = MemoryStore()
    it = ContentItem(source="xiaoyuzhou", external_id="a", title="T", url="u",
                     published_at="2026-06-13T16:00:00.000Z", is_paid=False, media_url="m",
                     image_url="https://image/x.jpg", show_title="非共识的20分钟")
    s.add(it)
    row = s.get("xiaoyuzhou", "a")
    assert row["image_url"] == "https://image/x.jpg"
    assert row["show_title"] == "非共识的20分钟"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_content_store.py -v`
Expected: FAIL — `KeyError: 'image_url'`

- [ ] **Step 3: Thread the fields through `store.py`**

In `store.py`, update `_row` and `_to_item` to include the two fields, and `PgStore` (schema CREATE + ALTER, INSERT).

`_row` (used by MemoryStore):
```python
def _row(item: ContentItem) -> dict:
    return {"source": item.source, "external_id": item.external_id, "title": item.title,
            "url": item.url, "published_at": item.published_at, "is_paid": item.is_paid,
            "media_url": item.media_url, "image_url": item.image_url,
            "show_title": item.show_title, "status": STATUS.NEW, "transcript": None,
            "signal_card": None, "error": None, "error_count": 0}
```

`_to_item`:
```python
def _to_item(row: dict) -> ContentItem:
    pub = row.get("published_at")
    return ContentItem(source=row["source"], external_id=row["external_id"],
                       title=row["title"], url=row["url"],
                       published_at=pub.isoformat() if hasattr(pub, "isoformat") else (pub or ""),
                       is_paid=row["is_paid"], media_url=row["media_url"],
                       image_url=row.get("image_url"), show_title=row.get("show_title"))
```

`PgStore.init_schema` — add the two columns to the `CREATE TABLE` body (after `media_url    TEXT,`):
```sql
                    media_url    TEXT,
                    image_url    TEXT,
                    show_title   TEXT,
```
and, immediately after the `CREATE INDEX ...` statement inside the same `cur.execute("""...""")` block, append idempotent ALTERs for already-deployed tables:
```sql
                CREATE INDEX IF NOT EXISTS content_items_status_idx
                    ON content_items(source, status);
                ALTER TABLE content_items ADD COLUMN IF NOT EXISTS image_url  TEXT;
                ALTER TABLE content_items ADD COLUMN IF NOT EXISTS show_title TEXT;
```

`PgStore.add` — add the columns to the INSERT:
```python
    def add(self, item: ContentItem):
        with _db() as c, c.cursor() as cur:
            cur.execute("""
                INSERT INTO content_items
                    (source, external_id, title, url, published_at, is_paid, media_url,
                     image_url, show_title, status)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'new')
                ON CONFLICT (source, external_id) DO NOTHING
            """, (item.source, item.external_id, item.title, item.url,
                  item.published_at or None, item.is_paid, item.media_url,
                  item.image_url, item.show_title))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/test_content_store.py -v`
Expected: PASS (6+ passed, 1 skipped)

- [ ] **Step 5: Run the whole pipeline suite (no regressions)**

Run: `$PYTEST tests/test_content_*.py -v`
Expected: all PASS (1 skipped)

- [ ] **Step 6: Commit**
```bash
git add content_pipeline/store.py tests/test_content_store.py
git commit -m "feat(signals): store image_url + show_title (additive columns)"
```

---

### Task 4: Backend — `_signal_row_to_dict` pure shaper

**Files:**
- Modify: `server/portfolio-api/app.py`
- Test: `server/portfolio-api/tests/test_app.py`

- [ ] **Step 1: Write the failing test (append to test_app.py)**
```python
def test_signal_row_to_dict_shapes_card_meta_no_transcript():
    row = {"external_id": "e1", "source": "xiaoyuzhou", "show_title": "非共识的20分钟",
           "image_url": "http://img/x.jpg", "title": "Ep 7", "url": "http://u",
           "published_at": None, "signal_card": {"tldr": "t", "pillar": "资金传导"}}
    d = app._signal_row_to_dict(row)
    assert d["card"]["pillar"] == "资金传导"
    assert d["show_title"] == "非共识的20分钟"
    assert d["image_url"] == "http://img/x.jpg"
    assert "transcript" not in d


def test_signal_row_to_dict_parses_str_card_and_includes_transcript():
    row = {"external_id": "e1", "signal_card": '{"tldr": "t"}', "transcript": "全文",
           "published_at": None}
    d = app._signal_row_to_dict(row, include_transcript=True)
    assert d["card"]["tldr"] == "t"
    assert d["transcript"] == "全文"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_app.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute '_signal_row_to_dict'`

- [ ] **Step 3: Add the helper to `app.py`**

Add near the other `v2` helpers (anywhere after `RDC = psycopg2.extras.RealDictCursor` is defined; `json` is already imported at the top of app.py):
```python
def _signal_row_to_dict(row: dict, include_transcript: bool = False) -> dict:
    """Shape a content_items row into the /api/signals payload. Pure (no I/O).
    signal_card is JSONB (psycopg2 → dict) but tolerate a JSON string too."""
    card = row.get("signal_card")
    if isinstance(card, str):
        try:
            card = json.loads(card)
        except ValueError:
            card = None
    pub = row.get("published_at")
    out = {
        "external_id": row.get("external_id"),
        "source": row.get("source"),
        "show_title": row.get("show_title"),
        "image_url": row.get("image_url"),
        "title": row.get("title"),
        "url": row.get("url"),
        "published_at": pub.isoformat() if hasattr(pub, "isoformat") else pub,
        "card": card,
    }
    if include_transcript:
        out["transcript"] = row.get("transcript")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/test_app.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**
```bash
git add app.py tests/test_app.py
git commit -m "feat(signals): _signal_row_to_dict payload shaper"
```

---

### Task 5: Backend — `/api/signals` + `/api/signals/<eid>` endpoints

**Files:**
- Modify: `server/portfolio-api/app.py`
- Test: `server/portfolio-api/tests/test_app.py`

- [ ] **Step 1: Write the failing test (append to test_app.py)**
```python
def test_signals_endpoints_require_login():
    client = app.app.test_client()
    assert client.get("/api/signals").status_code == 401
    assert client.get("/api/signals/anything").status_code == 401
```

- [ ] **Step 2: Run test to verify it fails**

Run: `$PYTEST tests/test_app.py::test_signals_endpoints_require_login -v`
Expected: FAIL — 404 (routes don't exist yet) instead of 401

- [ ] **Step 3: Add the endpoints to `app.py`**

Add after the company-analysis routes (any top-level route location is fine; `jsonify`, `request`, `_db`, `RDC`, `_current_user` are already in scope):
```python
# ---------- content signals (read-only feed over the pipeline's content_items) ----------

@app.get("/api/signals")
def list_signals():
    if not _current_user():
        return {"error": "未登录"}, 401
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute(
            "SELECT external_id, source, show_title, image_url, title, url, published_at, signal_card "
            "FROM content_items WHERE signal_card IS NOT NULL "
            "ORDER BY published_at DESC NULLS LAST LIMIT 50")
        rows = [dict(r) for r in cur.fetchall()]
    return jsonify({"items": [_signal_row_to_dict(r) for r in rows]})


@app.get("/api/signals/<eid>")
def get_signal(eid):
    if not _current_user():
        return {"error": "未登录"}, 401
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute(
            "SELECT external_id, source, show_title, image_url, title, url, published_at, "
            "signal_card, transcript FROM content_items "
            "WHERE external_id=%s AND signal_card IS NOT NULL", (eid,))
        r = cur.fetchone()
    if not r:
        return {"error": "not found"}, 404
    return jsonify(_signal_row_to_dict(dict(r), include_transcript=True))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `$PYTEST tests/test_app.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**
```bash
git add app.py tests/test_app.py
git commit -m "feat(signals): GET /api/signals + /api/signals/<eid> (read-only, login-gated)"
```

---

### Task 6: Frontend setup — deps, types, 小宇宙 logo asset

**Files:**
- Modify: `web/src/lib/types.ts`
- Create: `web/public/logos/xiaoyuzhou.png`

- [ ] **Step 1: Install frontend deps in the worktree**

Run (from `web/`):
```bash
npm install
```
Expected: completes; `node_modules/` present. (The worktree starts without it.)

- [ ] **Step 2: Add the 小宇宙 logo asset**

Run (from the worktree root):
```bash
mkdir -p web/public/logos
curl -sL "https://www.xiaoyuzhoufm.com/apple-touch-icon.png" -o web/public/logos/xiaoyuzhou.png
test -s web/public/logos/xiaoyuzhou.png && echo "logo ok ($(wc -c < web/public/logos/xiaoyuzhou.png) bytes)"
```
Expected: prints `logo ok (...)`. This ships with the SPA (served at `/logos/xiaoyuzhou.png`); the page never hot-links the platform site at runtime.

- [ ] **Step 3: Add types (append to `web/src/lib/types.ts`)**
```typescript
export interface SignalCard {
  tldr: string;
  non_consensus: string;
  new_angle: string;
  pillar: string;
  caution: string;
  worth_relisten: { yes: boolean; timestamps: string[] };
}

export interface Signal {
  external_id: string;
  source: string;
  show_title?: string | null;
  image_url?: string | null;
  title: string;
  url: string;
  published_at?: string | null;
  card: SignalCard;
}

export interface SignalDetail extends Signal {
  transcript?: string | null;
}
```

- [ ] **Step 4: Type-check passes**

Run (from `web/`): `npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 5: Commit**
```bash
git add web/src/lib/types.ts web/public/logos/xiaoyuzhou.png
git commit -m "feat(signals): frontend types + bundled 小宇宙 logo"
```

---

### Task 7: Frontend — `Signals.tsx` page

**Files:**
- Create: `web/src/pages/Signals.tsx`
- Test: `web/src/pages/Signals.test.tsx`

- [ ] **Step 1: Write the failing test**

`web/src/pages/Signals.test.tsx`:
```tsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

const sample = {
  external_id: "e7", source: "xiaoyuzhou", show_title: "非共识的20分钟",
  image_url: "http://img/cover.jpg", title: "美联储 Ep 7", url: "http://xyz/episode/e7",
  published_at: "2026-06-13T16:00:00.000Z",
  card: { tldr: "盯的不是利率", non_consensus: "市场问错了", new_angle: "盯隐藏变量",
          pillar: "资金传导", caution: "他重 crypto", worth_relisten: { yes: false, timestamps: [] } },
};

vi.mock("../lib/api", () => ({
  apiGet: vi.fn((p: string) =>
    p === "/api/signals"
      ? Promise.resolve({ ok: true, status: 200, data: { items: [sample] } })
      : Promise.resolve({ ok: true, status: 200, data: { ...sample, transcript: "转录全文内容" } })),
}));
vi.mock("../lib/hooks", () => ({ useMe: () => "lucas" }));

import Signals from "./Signals";

describe("Signals", () => {
  beforeEach(() => vi.clearAllMocks());

  it("renders a signal card with title, pillar and tldr", async () => {
    render(<Signals />);
    expect(await screen.findByText("美联储 Ep 7")).toBeInTheDocument();
    expect(screen.getByText("资金传导")).toBeInTheDocument();
    expect(screen.getByText(/盯的不是利率/)).toBeInTheDocument();
  });

  it("expands to show the 6 fields and lazy-loads transcript", async () => {
    const { apiGet } = await import("../lib/api");
    render(<Signals />);
    fireEvent.click(await screen.findByText("美联储 Ep 7"));
    expect(await screen.findByText(/市场问错了/)).toBeInTheDocument();   // non_consensus revealed
    fireEvent.click(screen.getByText(/转录全文/));
    await waitFor(() => expect(screen.getByText(/转录全文内容/)).toBeInTheDocument());
    expect(apiGet).toHaveBeenCalledWith("/api/signals/e7");
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `web/`): `npx vitest run src/pages/Signals.test.tsx --reporter=default`
Expected: FAIL — cannot resolve `./Signals`.

- [ ] **Step 3: Write `Signals.tsx`**

`web/src/pages/Signals.tsx`:
```tsx
import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";
import { useMe } from "../lib/hooks";
import type { Signal, SignalDetail } from "../lib/types";

// source-type tabs = the 板块 structure. v1 wires only 播客.
const TABS = [
  { key: "podcast", label: "🎧 播客", soon: false },
  { key: "news", label: "📰 消息面 · 金十", soon: true },
  { key: "twitter", label: "🐦 推特", soon: true },
  { key: "data", label: "📊 数据", soon: true },
];
const XYZ_LOGO = "/logos/xiaoyuzhou.png";

function fmtDate(s?: string | null): string {
  if (!s) return "";
  const d = new Date(s);
  return Number.isNaN(d.getTime()) ? "" : `${d.getMonth() + 1}/${d.getDate()}`;
}

function Card({ sig }: { sig: Signal }) {
  const [open, setOpen] = useState(false);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [showTrx, setShowTrx] = useState(false);
  const c = sig.card;

  async function toggleTranscript() {
    setShowTrx((v) => !v);
    if (transcript === null) {
      const r = await apiGet<SignalDetail>(`/api/signals/${sig.external_id}`);
      setTranscript(r.data?.transcript ?? "（该集暂无转录）");
    }
  }

  return (
    <div className={`sig${open ? " open" : ""}`}>
      <div className="sig-top" onClick={() => setOpen((v) => !v)}>
        <img className="thumb" src={sig.image_url || XYZ_LOGO} alt="" />
        <div className="sig-main">
          <h3 className="ttl">{sig.title}</h3>
          <div className="sig-meta">
            <span className="pill">{c.pillar || "—"}</span>
            <span className="src"><img src={XYZ_LOGO} alt="小宇宙" />{sig.show_title || "—"}</span>
            <span>· {fmtDate(sig.published_at)}</span>
          </div>
          <p className="sig-snip"><b>主旨</b>:{c.tldr || "—"}</p>
        </div>
        <span className="chev">▾</span>
      </div>
      {open && (
        <div className="sig-body">
          <p className="fld"><span className="k">非共识</span>{c.non_consensus || "—"}</p>
          <p className="fld"><span className="k">给你的新角度</span>{c.new_angle || "—"}</p>
          <p className="fld warn"><span className="k">⚠️ 该警惕什么</span>{c.caution || "—"}</p>
          <p className="relisten">回听原集:<b>{c.worth_relisten?.yes ? "是" : "否"}</b>
            {c.worth_relisten?.timestamps?.length ? `（${c.worth_relisten.timestamps.join("、")}）` : ""}</p>
          <div className="acts">
            <a className="btn" href={sig.url} target="_blank" rel="noreferrer">🔗 到小宇宙听原集</a>
            <button className="btn" onClick={toggleTranscript}>📄 转录全文 ▾</button>
          </div>
          {showTrx && (
            <div className="trx">
              <span className="note">机器转录(faster-whisper),可能有错字。</span>
              {transcript ?? "加载中…"}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function Signals() {
  const user = useMe();
  const [items, setItems] = useState<Signal[]>([]);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    apiGet<{ items: Signal[] }>("/api/signals").then((r) => {
      setItems(r.data?.items ?? []);
      setLoaded(true);
    });
  }, []);

  const show = items[0]?.show_title || "非共识的20分钟";

  return (
    <>
      <div className="app-head">
        <div className="eyebrow">VALUE INVESTING · 信号流</div>
        <h1>📡 信号</h1>
        <p>把各处信号源替你过滤,只留<b>非共识</b>的部分——你花的是读 signal 的时间,不是刷信息的时间。</p>
      </div>

      <div className="sig-tabs">
        {TABS.map((t) => (
          <span key={t.key} className={`sig-tab${t.soon ? " soon" : " active"}`}>
            {t.label}{t.soon && <i>即将</i>}
          </span>
        ))}
      </div>

      <div className="sig-lane">
        <img className="logo" src={XYZ_LOGO} alt="小宇宙" />
        <span className="lane-t">小宇宙</span>
        <span className="lane-s">· {show} · 每天 08:00 自动更新</span>
      </div>

      {user === null && <p className="status">登录后查看信号。</p>}
      {loaded && items.length === 0 && user && (
        <p className="status">还没有信号卡——管道每天 08:00 自动更新。</p>
      )}

      <div className="sig-list">
        {items.map((s) => <Card key={s.external_id} sig={s} />)}
      </div>
    </>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run (from `web/`): `npx vitest run src/pages/Signals.test.tsx --reporter=default`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**
```bash
git add web/src/pages/Signals.tsx web/src/pages/Signals.test.tsx
git commit -m "feat(signals): Signals page (cards + expand + lazy transcript)"
```

---

### Task 8: Frontend — styles for the signals page

**Files:**
- Modify: `web/src/styles/global.css`

(No unit test — visual CSS. Verified by the type-check/build in Task 9 and manual view.)

- [ ] **Step 1: Append the signals block to `global.css`**

Add at the end of `web/src/styles/global.css`:
```css
/* ===== 信号 hub ===== */
.sig-tabs { display: flex; gap: 8px; flex-wrap: wrap; margin: 16px 0 6px; border-bottom: 1px solid var(--border); padding-bottom: 12px; }
.sig-tab { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; padding: 7px 13px; border-radius: 9px; border: 1px solid var(--border); background: var(--bg-soft); color: var(--fg-soft); }
.sig-tab.active { color: var(--accent); border-color: var(--accent); background: var(--accent-soft); }
.sig-tab.soon { color: var(--muted); opacity: .7; }
.sig-tab.soon i { font-style: normal; font-size: 10.5px; background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 0 6px; margin-left: 2px; }
.sig-lane { display: flex; align-items: center; gap: 9px; margin: 22px 0 12px; }
.sig-lane .logo { width: 22px; height: 22px; border-radius: 6px; }
.sig-lane .lane-t { font-size: 15px; font-weight: 700; color: var(--fg); }
.sig-lane .lane-s { font-size: 12.5px; color: var(--muted); }
.sig-list { display: flex; flex-direction: column; gap: 14px; }
.sig { background: var(--bg-soft); border: 1px solid var(--border); border-radius: 12px; padding: 15px 18px; transition: border-color var(--t), box-shadow var(--t); }
.sig:hover { border-color: var(--accent); box-shadow: var(--shadow-1); }
.sig-top { display: flex; align-items: flex-start; gap: 14px; cursor: pointer; }
.sig .thumb { width: 60px; height: 60px; border-radius: 10px; object-fit: cover; border: 1px solid var(--border); flex-shrink: 0; background: var(--bg); }
.sig-main { flex: 1; min-width: 0; }
.sig .ttl { font-size: 16px; font-weight: 600; color: var(--fg); margin: 0; line-height: 1.4; }
.sig-meta { margin-top: 7px; font-size: 12px; color: var(--muted); display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.sig-meta .pill { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; background: var(--accent-soft); color: var(--accent); }
.sig-meta .src { display: inline-flex; align-items: center; gap: 4px; color: var(--muted); }
.sig-meta .src img { width: 13px; height: 13px; border-radius: 3px; }
.sig .chev { color: var(--muted); font-size: 13px; flex-shrink: 0; transition: transform var(--t); align-self: center; }
.sig.open .chev { transform: rotate(180deg); }
.sig-snip { margin: 9px 0 0; font-size: 13.5px; color: var(--fg-soft); line-height: 1.6; }
.sig-snip b { color: var(--fg); }
.sig-body { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--border); }
.sig-body .fld { margin: 0 0 12px; font-size: 14px; line-height: 1.7; color: var(--fg-soft); }
.sig-body .fld .k { display: block; font-size: 12px; font-weight: 700; letter-spacing: .04em; color: var(--accent); margin-bottom: 3px; }
.sig-body .fld.warn .k { color: var(--warn); }
.sig-body .relisten { font-size: 13px; color: var(--muted); margin: 2px 0 0; }
.sig-body .acts { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 14px; }
.sig-body .trx { margin-top: 12px; background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px; padding: 13px 15px; font-size: 13.5px; line-height: 1.75; color: var(--fg-soft); white-space: pre-wrap; }
.sig-body .trx .note { display: block; color: var(--muted); font-size: 12px; margin-bottom: 8px; font-style: italic; }
```

- [ ] **Step 2: Re-run the page test (still green with classes present)**

Run (from `web/`): `npx vitest run src/pages/Signals.test.tsx --reporter=default`
Expected: PASS (2 tests).

- [ ] **Step 3: Commit**
```bash
git add web/src/styles/global.css
git commit -m "feat(signals): styles for the 信号 page (tokens-based)"
```

---

### Task 9: Frontend — wire route + nav

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/app/Nav.tsx`

- [ ] **Step 1: Add the lazy import + route in `App.tsx`**

Add the lazy import alongside the others:
```typescript
const Signals = lazy(() => import("./pages/Signals"));
```
Add the route inside the `Layout` `children` array (e.g. after the `/analyze` route):
```typescript
      { path: "/signals", element: <Signals /> },
```

- [ ] **Step 2: Add the nav item in `Nav.tsx`**

Add to the `ITEMS` array (after `["/analyze", "🏢 公司分析"]`):
```typescript
  ["/signals", "📡 信号"],
```

- [ ] **Step 3: Type-check (verifies the lazy import path + route compile)**

Run (from `web/`):
```bash
npx tsc --noEmit
```
Expected: no errors. (The full production build runs at deploy time via `web/deploy.sh` → `npm run build`.)

- [ ] **Step 4: Run the whole frontend test suite (no regressions)**

Run (from `web/`): `npx vitest run --reporter=default`
Expected: all PASS (existing tests + the 2 new Signals tests).

- [ ] **Step 5: Commit**
```bash
git add web/src/App.tsx web/src/app/Nav.tsx
git commit -m "feat(signals): wire /signals route + 📡 信号 nav item"
```

---

### Task 10: Deploy runbook + backfill (one-time)

**Files:**
- Create: `server/portfolio-api/content_pipeline/backfill_image.py`

This task ships the work to prod. The backfill is real code (fills `image_url`/`show_title` for already-processed rows like Ep7, whose columns are NULL).

- [ ] **Step 1: Write the backfill script**

`server/portfolio-api/content_pipeline/backfill_image.py`:
```python
#!/usr/bin/env python3
"""One-time backfill: set image_url + show_title on existing content_items rows
from the live podcast page. Safe to re-run (idempotent UPDATE by key). Run on the
server with VI_DATABASE_URL set: `venv/bin/python -m content_pipeline.backfill_image`."""
from __future__ import annotations

import os

from content_pipeline.adapters.xiaoyuzhou import XiaoyuzhouAdapter
from content_pipeline.store import _db  # reuse the same connection contextmanager


def main() -> int:
    pid = os.environ.get("VI_PIPELINE_PODCAST_ID", "6978a31df828d4e9f2787d3d")
    items = XiaoyuzhouAdapter(pid).list_items()
    n = 0
    with _db() as c, c.cursor() as cur:
        for it in items:
            cur.execute(
                "UPDATE content_items SET image_url=COALESCE(image_url,%s), "
                "show_title=COALESCE(show_title,%s) WHERE source=%s AND external_id=%s",
                (it.image_url, it.show_title, it.source, it.external_id))
            n += cur.rowcount
    print(f"backfilled {n} rows (image_url/show_title where missing)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Verify it imports locally (no DB needed to import)**

Run (from `server/portfolio-api/`):
```bash
/Users/Zhuanz/Documents/code/value-investment/server/portfolio-api/.venv/bin/python -c "import content_pipeline.backfill_image; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 3: Commit**
```bash
git add content_pipeline/backfill_image.py
git commit -m "feat(signals): one-time image_url/show_title backfill script"
```

- [ ] **Step 4: Deploy (manual, after the branch is merged) — runbook**

Pipeline + schema + backfill (server):
```bash
# from the worktree root
rsync -avz --exclude='__pycache__' -e ssh server/portfolio-api/content_pipeline/ \
  openclaw:/opt/value-investment-api/content_pipeline/
ssh openclaw "bash -lc 'set -a; . /etc/value-investment/api.env; set +a; cd /opt/value-investment-api; \
  venv/bin/python -c \"from content_pipeline.store import PgStore; PgStore().init_schema(); print(\\\"schema ok\\\")\"; \
  venv/bin/python -m content_pipeline.backfill_image'"
```
Backend API (adds the two endpoints; setup-api.sh copies `*.py` + restarts):
```bash
rsync -avz -e ssh server/ openclaw:/root/vi-server/
ssh openclaw "bash /root/vi-server/portfolio-api/setup-api.sh"
ssh openclaw "curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8787/api/health"
```
Frontend (build + rsync the SPA):
```bash
./web/deploy.sh
```
Verify: log in at the site → `📡 信号` → the Ep7 card shows with cover art; expand → fields + transcript.

---

## Definition of Done (maps to spec acceptance)

1. ✅ `/signals` page: hub header (source-agnostic) + tabs (播客 active, others 即将) + 小宇宙 栏 — Tasks 7–9.
2. ✅ At least the real Ep7 card with cover thumb + 资金传导 chip + tldr — Tasks 5,7 + backfill Task 10.
3. ✅ Expand → 6 fields + 原集链接; transcript lazy-loads — `Signals.test.tsx` (Task 7).
4. ✅ Paid/no-card omitted (`WHERE signal_card IS NOT NULL`); NULL image falls back to logo — Tasks 5,7.
5. ✅ Endpoints login-gated + read-only; new columns additive + backfilled — Tasks 3,5,10.
6. ✅ Styling consistent (tokens) + new `📡 信号` nav — Tasks 8,9.
7. ✅ Other tabs are static "即将", no errors — Task 7 (`soon` tabs render, not wired).
```
