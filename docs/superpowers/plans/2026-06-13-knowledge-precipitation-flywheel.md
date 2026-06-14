# Knowledge Precipitation Flywheel (Subsystem B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture a thought (Feishu/web) → hermes decides it's worth keeping → calls a `capture_note` MCP tool → backend deterministically files it into a 3-database Notion knowledge base with dedup + slug back-links, buffered in Postgres so nothing is lost; hermes grows its understanding of the user via its native memory loop.

**Architecture:** hermes is the brain (decides when to capture, structures the note); the Flask backend is the hands (deterministic Notion write, dedup, Fernet-stored token, Postgres buffer). hermes reaches the backend through an MCP tool. Read-back closes the flywheel: cheap Postgres recent-context injection (mechanism A) + hermes native memory (mechanism B, configured not built). Structured facts stay Postgres-injected, never in memory.

**Tech Stack:** Python 3 / Flask / psycopg2 / PostgreSQL (existing backend), `notion-client` SDK, hermes v0.16 MCP + skills + memory, pytest + tdd-guard-pytest (already installed). Spec: `docs/superpowers/specs/2026-06-13-knowledge-precipitation-flywheel-design.md`.

---

## File Structure

All backend work lives in `server/portfolio-api/` (existing single-package Flask app; follow its patterns — `_db()` contextmanager, `_enc_secret`/`_dec_secret`, module-level `_init_db()`).

| File | New/Mod | Responsibility |
|---|---|---|
| `server/portfolio-api/notion_kb.py` | **New** | NotionClient protocol + `RealNotionClient` (Notion API adapter). Low-level page/db ops only. |
| `server/portfolio-api/capture.py` | **New** | The write-flow: note→property mapping (pure), concept/source dedup, slug back-fill, `record_capture` orchestration, `retry_pending`. The testable heart. |
| `server/portfolio-api/mcp_server.py` | **New** | MCP server exposing `capture_note` / `list_concepts` / `list_sources`. Thin wrapper over `capture.py`. |
| `server/portfolio-api/app.py` | **Mod** | Add `captures`/`kb_concepts`/`kb_sources` tables to `_init_db()`; Notion token storage (reuse Fernet); recent-context (mechanism A) in `_build_learner_profile`. |
| `server/portfolio-api/tests/test_capture.py` | **New** | pytest for the pure/deterministic core (mapping, dedup, slug, idempotency, error state). |
| `server/portfolio-api/tests/conftest.py` | **New** | `FakeNotionClient` + in-memory/sqlite-free fixtures so tests need no real Notion. |
| `skills/vi-capture-note/SKILL.md` | **New** | Skill guiding hermes to structure a capture for our Notion schema. Auto-seeded to PG + profiles via existing `seed.py`/`provision_hermes`. |

Config/ops (no code, documented tasks): create 3 Notion databases + record ids; `hermes mcp add` the capture server to `app-*` profiles; SOUL addition; enable `memory` toolset.

---

## Phase 0 — Setup (Notion workspace + deps)

### Task 0.1: Create the 3 Notion databases, record their ids

**Files:** none (Notion UI + an env file)

- [ ] **Step 1: In Notion, create a parent page "VI 知识库" and 3 inline databases** with exactly these properties (types matter for the API):
  - **Notes**: `标题`(title), `内容`(text), `情境`(select: 自己想的/闲聊/播客/书/文章/会议/其他), `概念`(relation→Concepts), `来源`(relation→Sources), `类型`(select: 思考/要点/疑问/反例/行动), `标签`(multi_select), `时间`(date)
  - **Concepts**: `名称`(title), `定义`(text), `术语slug`(text), `笔记`(relation→Notes, the back-reference auto-created)
  - **Sources**: `标题`(title), `类型`(select: 书/播客/letter/文章), `作者`(text), `URL`(url), `canon_slug`(text), `笔记`(relation→Notes)
- [ ] **Step 2: Create a Notion internal integration** at https://www.notion.so/my-integrations, copy the token (starts `ntn_` / `secret_`), and **share all 3 databases with the integration** (each DB → ⋯ → Connections → your integration).
- [ ] **Step 3: Copy each database id** (the 32-char hex in the DB URL) into a scratch note. You'll store them in Step 0.2.

Verify: opening each DB URL shows the database; the integration appears under each DB's Connections.

### Task 0.2: Add deps + a config block for Notion ids/token location

**Files:**
- Modify: `server/portfolio-api/requirements.txt`
- Modify: `server/portfolio-api/requirements-dev.txt` (none needed; pytest already there)

- [ ] **Step 1: Add the Notion SDK to prod requirements**

`server/portfolio-api/requirements.txt` — append:
```
notion-client>=2.2
```

- [ ] **Step 2: Install into the test venv**

Run:
```bash
cd server/portfolio-api && ./.venv/bin/pip install -r requirements.txt
```
Expected: `notion-client` installs cleanly.

- [ ] **Step 3: Decide config surface.** Notion db ids are non-secret → env vars `VI_NOTION_DB_NOTES`, `VI_NOTION_DB_CONCEPTS`, `VI_NOTION_DB_SOURCES`. The Notion **token is secret** → stored Fernet-encrypted in Postgres (Task 2.3), NOT an env var. Document this in `server/portfolio-api/app.py` header comment block (where the other `VI_*` env vars are listed).

- [ ] **Step 4: Commit**
```bash
git add server/portfolio-api/requirements.txt
git commit -m "chore: add notion-client dep for knowledge capture"
```

---

## Phase 1 — Capture write-flow core (TDD, no Notion/hermes needed)

This is the deterministic heart. We TDD it against a `FakeNotionClient`, so every test runs locally with no real Notion.

### Task 1.1: Postgres schema for captures + concept/source index

**Files:**
- Modify: `server/portfolio-api/app.py` (inside `_init_db()`, alongside the other `CREATE TABLE IF NOT EXISTS`)

- [ ] **Step 1: Add the three tables to `_init_db()`**

In `server/portfolio-api/app.py`, inside `_init_db()`'s cursor block, add:
```python
        cur.execute("""
            CREATE TABLE IF NOT EXISTS captures (
                id             SERIAL PRIMARY KEY,
                username       TEXT NOT NULL,
                raw            TEXT NOT NULL,
                title          TEXT,
                note_type      TEXT,
                situation      TEXT,
                tags           JSONB DEFAULT '[]',
                notion_page_id TEXT,
                status         TEXT NOT NULL DEFAULT 'pending',   -- pending | written | error
                error          TEXT,
                created_at     TIMESTAMPTZ DEFAULT now(),
                written_at     TIMESTAMPTZ
            )""")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_concepts (
                id             SERIAL PRIMARY KEY,
                username       TEXT NOT NULL,
                name           TEXT NOT NULL,
                notion_page_id TEXT,
                term_slug      TEXT
            )""")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS kb_concepts_uq ON kb_concepts (username, lower(name))")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS kb_sources (
                id             SERIAL PRIMARY KEY,
                username       TEXT NOT NULL,
                title          TEXT NOT NULL,
                kind TEXT, author TEXT, url TEXT,
                notion_page_id TEXT,
                canon_slug     TEXT
            )""")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS kb_sources_uq ON kb_sources (username, lower(title))")
```

- [ ] **Step 2: Verify the module still imports without a DB** (DB_URL empty → `_init_db` short-circuits)

Run:
```bash
cd server/portfolio-api && ./.venv/bin/python -c "import app; print('ok')"
```
Expected: `ok` (no DB connection at import).

- [ ] **Step 3: Commit**
```bash
git add server/portfolio-api/app.py
git commit -m "feat(capture): captures + kb_concepts + kb_sources tables"
```

### Task 1.2: Pure note→Notion-property mapping

**Files:**
- Create: `server/portfolio-api/capture.py`
- Test: `server/portfolio-api/tests/test_capture.py`

- [ ] **Step 1: Write the failing test**

`server/portfolio-api/tests/test_capture.py`:
```python
from capture import map_note_properties


def test_map_note_properties_builds_notion_shape():
    cap = {
        "title": "波动不是风险",
        "clean_content": "他把波动当风险，其实风险是永久损失。",
        "situation": "播客",
        "note_type": "思考",
        "tags": ["风险", "安全边际"],
    }
    props = map_note_properties(cap, concept_ids=["c1", "c2"], source_id="s1", created_iso="2026-06-13T00:00:00+00:00")
    assert props["标题"] == {"title": [{"text": {"content": "波动不是风险"}}]}
    assert props["内容"] == {"rich_text": [{"text": {"content": "他把波动当风险，其实风险是永久损失。"}}]}
    assert props["情境"] == {"select": {"name": "播客"}}
    assert props["类型"] == {"select": {"name": "思考"}}
    assert props["标签"] == {"multi_select": [{"name": "风险"}, {"name": "安全边际"}]}
    assert props["概念"] == {"relation": [{"id": "c1"}, {"id": "c2"}]}
    assert props["来源"] == {"relation": [{"id": "s1"}]}
    assert props["时间"] == {"date": {"start": "2026-06-13T00:00:00+00:00"}}


def test_map_note_properties_omits_empty_relations():
    cap = {"title": "t", "clean_content": "c", "situation": "自己想的", "note_type": "思考", "tags": []}
    props = map_note_properties(cap, concept_ids=[], source_id=None, created_iso="2026-06-13T00:00:00+00:00")
    assert "来源" not in props          # no source → no relation key
    assert props["概念"] == {"relation": []}
    assert props["标签"] == {"multi_select": []}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'capture'` (or import error).

- [ ] **Step 3: Write minimal implementation**

`server/portfolio-api/capture.py`:
```python
"""Knowledge-capture write flow: map → dedup → file into Notion, buffered in Postgres.
Pure logic + a NotionClient seam so it's fully unit-testable without a real Notion."""
from __future__ import annotations


def map_note_properties(cap: dict, concept_ids: list[str], source_id: str | None, created_iso: str) -> dict:
    """Build a Notion `properties` dict for a Notes-database page from a capture JSON."""
    props: dict = {
        "标题": {"title": [{"text": {"content": cap.get("title", "")}}]},
        "内容": {"rich_text": [{"text": {"content": cap.get("clean_content", "")}}]},
        "情境": {"select": {"name": cap.get("situation", "其他")}},
        "类型": {"select": {"name": cap.get("note_type", "思考")}},
        "标签": {"multi_select": [{"name": t} for t in (cap.get("tags") or [])]},
        "概念": {"relation": [{"id": cid} for cid in concept_ids]},
        "时间": {"date": {"start": created_iso}},
    }
    if source_id:
        props["来源"] = {"relation": [{"id": source_id}]}
    return props
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py -q`
Expected: PASS (2 passed). NOTE: TDD Guard enforces one test at a time — if it blocks, split Step 1 into the first test only, pass it, then add the second test in a follow-up commit.

- [ ] **Step 5: Commit**
```bash
git add server/portfolio-api/capture.py server/portfolio-api/tests/test_capture.py
git commit -m "feat(capture): pure note→Notion property mapping"
```

### Task 1.3: FakeNotionClient fixture + NotionClient seam

**Files:**
- Create: `server/portfolio-api/notion_kb.py` (the protocol only, for now)
- Create: `server/portfolio-api/tests/conftest.py`

- [ ] **Step 1: Define the NotionClient protocol**

`server/portfolio-api/notion_kb.py`:
```python
"""Notion adapter. The protocol is the seam capture.py depends on; RealNotionClient
(Task 2.x) implements it against the Notion API. Tests use FakeNotionClient."""
from __future__ import annotations
from typing import Protocol


class NotionClient(Protocol):
    def create_page(self, db_id: str, properties: dict) -> str:
        """Create a page in db_id, return the new page id."""
        ...

    def update_page(self, page_id: str, properties: dict) -> None:
        """Patch properties on an existing page."""
        ...
```

- [ ] **Step 2: Add the FakeNotionClient fixture**

`server/portfolio-api/tests/conftest.py`:
```python
import itertools
import pytest


class FakeNotionClient:
    """In-memory NotionClient: records created/updated pages, hands out incrementing ids."""
    def __init__(self):
        self.pages: dict[str, dict] = {}
        self._ids = (f"pg{n}" for n in itertools.count(1))

    def create_page(self, db_id: str, properties: dict) -> str:
        pid = next(self._ids)
        self.pages[pid] = {"db_id": db_id, "properties": dict(properties)}
        return pid

    def update_page(self, page_id: str, properties: dict) -> None:
        self.pages[page_id]["properties"].update(properties)


@pytest.fixture
def notion():
    return FakeNotionClient()
```

- [ ] **Step 3: Verify the fixture loads (no test yet, just import sanity)**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/ -q`
Expected: PASS (still 2 passed from Task 1.2; conftest imports cleanly).

- [ ] **Step 4: Commit**
```bash
git add server/portfolio-api/notion_kb.py server/portfolio-api/tests/conftest.py
git commit -m "test(capture): NotionClient protocol + FakeNotionClient fixture"
```

### Task 1.4: Concept dedup + create (find-or-create against a fake DB index)

To keep dedup pure-testable, `capture.py` takes an **index object** (not a live psycopg2 conn). Define a tiny `KbIndex` protocol with `find_concept(user, name)` / `add_concept(...)`; tests use an in-memory fake, prod uses a Postgres-backed impl (Task 2.x).

**Files:**
- Modify: `server/portfolio-api/notion_kb.py` (add `KbIndex` protocol)
- Modify: `server/portfolio-api/capture.py` (add `find_or_create_concept`)
- Modify: `server/portfolio-api/tests/conftest.py` (add `FakeKbIndex`)
- Modify: `server/portfolio-api/tests/test_capture.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_capture.py`:
```python
from capture import find_or_create_concept


def test_find_or_create_concept_creates_then_reuses(notion, kb):
    cid1 = find_or_create_concept(kb, notion, "lucas", "安全边际", one_liner="远低于内在价值买入",
                                  concepts_db_id="DBC", term_slug="margin-of-safety")
    # second time, same name (different case/space) → reuse, no new page
    n_before = len(notion.pages)
    cid2 = find_or_create_concept(kb, notion, "lucas", " 安全边际 ", one_liner="x",
                                  concepts_db_id="DBC", term_slug=None)
    assert cid1 == cid2
    assert len(notion.pages) == n_before          # no duplicate page created
    # the created page carried the term_slug back-fill
    assert notion.pages[cid1]["properties"]["术语slug"] == {"rich_text": [{"text": {"content": "margin-of-safety"}}]}
```

- [ ] **Step 2: Add `FakeKbIndex` + `kb` fixture**

Append to `tests/conftest.py`:
```python
class FakeKbIndex:
    def __init__(self):
        self.concepts: dict[tuple, dict] = {}   # (user, lower(name)) -> {page_id, term_slug}
        self.sources: dict[tuple, dict] = {}

    def find_concept(self, user, name):
        return self.concepts.get((user, name.strip().lower()))

    def add_concept(self, user, name, page_id, term_slug):
        self.concepts[(user, name.strip().lower())] = {"page_id": page_id, "term_slug": term_slug}

    def find_source(self, user, title):
        return self.sources.get((user, title.strip().lower()))

    def add_source(self, user, title, page_id, canon_slug):
        self.sources[(user, title.strip().lower())] = {"page_id": page_id, "canon_slug": canon_slug}


@pytest.fixture
def kb():
    return FakeKbIndex()
```

- [ ] **Step 3: Add the `KbIndex` protocol to `notion_kb.py`**
```python
class KbIndex(Protocol):
    def find_concept(self, user: str, name: str) -> dict | None: ...
    def add_concept(self, user: str, name: str, page_id: str, term_slug: str | None) -> None: ...
    def find_source(self, user: str, title: str) -> dict | None: ...
    def add_source(self, user: str, title: str, page_id: str, canon_slug: str | None) -> None: ...
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py::test_find_or_create_concept_creates_then_reuses -q`
Expected: FAIL — `find_or_create_concept` not defined.

- [ ] **Step 5: Implement `find_or_create_concept`**

Append to `capture.py`:
```python
def find_or_create_concept(kb, notion, user: str, name: str, one_liner: str,
                           concepts_db_id: str, term_slug: str | None) -> str:
    """Return the Notion page id for a concept, creating + indexing it if new."""
    name = (name or "").strip()
    hit = kb.find_concept(user, name)
    if hit:
        return hit["page_id"]
    props = {
        "名称": {"title": [{"text": {"content": name}}]},
        "定义": {"rich_text": [{"text": {"content": one_liner or ""}}]},
    }
    if term_slug:
        props["术语slug"] = {"rich_text": [{"text": {"content": term_slug}}]}
    page_id = notion.create_page(concepts_db_id, props)
    kb.add_concept(user, name, page_id, term_slug)
    return page_id
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**
```bash
git add server/portfolio-api/capture.py server/portfolio-api/notion_kb.py server/portfolio-api/tests/
git commit -m "feat(capture): concept find-or-create with dedup + slug back-fill"
```

### Task 1.5: Source find-or-create (optional source, same dedup pattern)

**Files:** Modify `server/portfolio-api/capture.py`, `tests/test_capture.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_capture.py`:
```python
from capture import find_or_create_source


def test_find_or_create_source_dedupes_by_title(notion, kb):
    src = {"title": "纵横四海 EP100", "kind": "播客", "author": "劲波", "url": "https://x"}
    sid1 = find_or_create_source(kb, notion, "lucas", src, sources_db_id="DBS", canon_slug=None)
    sid2 = find_or_create_source(kb, notion, "lucas", {"title": "纵横四海 EP100"}, sources_db_id="DBS", canon_slug=None)
    assert sid1 == sid2
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py::test_find_or_create_source_dedupes_by_title -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `capture.py`:
```python
def find_or_create_source(kb, notion, user: str, src: dict, sources_db_id: str, canon_slug: str | None) -> str:
    title = (src.get("title") or "").strip()
    hit = kb.find_source(user, title)
    if hit:
        return hit["page_id"]
    props = {"标题": {"title": [{"text": {"content": title}}]}}
    if src.get("kind"):
        props["类型"] = {"select": {"name": src["kind"]}}
    if src.get("author"):
        props["作者"] = {"rich_text": [{"text": {"content": src["author"]}}]}
    if src.get("url"):
        props["URL"] = {"url": src["url"]}
    if canon_slug:
        props["canon_slug"] = {"rich_text": [{"text": {"content": canon_slug}}]}
    page_id = notion.create_page(sources_db_id, props)
    kb.add_source(user, title, page_id, canon_slug)
    return page_id
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/portfolio-api/capture.py server/portfolio-api/tests/test_capture.py
git commit -m "feat(capture): source find-or-create with dedup"
```

### Task 1.6: `record_capture` orchestration (the public entry)

`record_capture` ties it together: resolve concepts (with slug back-fill via a `slug_lookup` callback so it stays DB-agnostic) + optional source, create the Note page, return a receipt. Persisting to the `captures` table is the Postgres-backed `KbIndex` impl's job (Task 2.x) — here we keep `record_capture` testable by returning the structured result and letting the caller persist.

**Files:** Modify `server/portfolio-api/capture.py`, `tests/test_capture.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_capture.py`:
```python
from capture import record_capture

DB_IDS = {"notes": "DBN", "concepts": "DBC", "sources": "DBS"}


def test_record_capture_files_note_with_links(notion, kb):
    cap = {
        "title": "波动≠风险", "clean_content": "...", "situation": "播客", "note_type": "思考",
        "tags": ["风险"],
        "concepts": [{"name": "安全边际", "existing": False, "one_liner": "..."}],
        "source": {"title": "纵横四海 EP100", "kind": "播客"},
        "insight": "他总把波动当风险",
    }
    # slug_lookup: concept name → glossary slug; source title → canon slug (None here)
    res = record_capture(kb, notion, "lucas", cap, DB_IDS,
                         slug_lookup=lambda kind, key: "margin-of-safety" if kind == "concept" else None,
                         created_iso="2026-06-13T00:00:00+00:00")
    note = notion.pages[res["notion_page_id"]]
    assert note["db_id"] == "DBN"
    assert note["properties"]["概念"]["relation"]                 # linked to the new concept
    assert note["properties"]["来源"]["relation"]                 # linked to the new source
    assert "已记" in res["receipt"]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py::test_record_capture_files_note_with_links -q`
Expected: FAIL.

- [ ] **Step 3: Implement**

Append to `capture.py`:
```python
def record_capture(kb, notion, user: str, cap: dict, db_ids: dict, slug_lookup, created_iso: str) -> dict:
    """Resolve concepts/source, create the Note page, return {notion_page_id, concept_ids, source_id, receipt}."""
    concept_ids = []
    for c in (cap.get("concepts") or []):
        slug = slug_lookup("concept", c["name"])
        concept_ids.append(find_or_create_concept(
            kb, notion, user, c["name"], c.get("one_liner", ""), db_ids["concepts"], slug))
    source_id = None
    src = cap.get("source")
    if src and src.get("title"):
        source_id = find_or_create_source(
            kb, notion, user, src, db_ids["sources"], slug_lookup("source", src["title"]))
    props = map_note_properties(cap, concept_ids, source_id, created_iso)
    note_id = notion.create_page(db_ids["notes"], props)
    cnames = "·".join(c["name"] for c in (cap.get("concepts") or [])) or "—"
    receipt = f"✅ 已记:〈{cap.get('title', '')}〉· 概念 {cnames}"
    return {"notion_page_id": note_id, "concept_ids": concept_ids, "source_id": source_id, "receipt": receipt}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_capture.py -q`
Expected: PASS (all capture tests green).

- [ ] **Step 5: Commit**
```bash
git add server/portfolio-api/capture.py server/portfolio-api/tests/test_capture.py
git commit -m "feat(capture): record_capture orchestration (concepts+source+note)"
```

---

## Phase 2 — Real Notion adapter, token storage, Postgres KbIndex

Now wire the seams to real infrastructure. These are integration tasks: verified against a real Notion test DB, not unit tests.

### Task 2.1: RealNotionClient

**Files:** Modify `server/portfolio-api/notion_kb.py`

- [ ] **Step 1: Implement RealNotionClient over the `notion-client` SDK**

Append to `notion_kb.py`:
```python
from notion_client import Client as _Notion


class RealNotionClient:
    def __init__(self, token: str):
        self._c = _Notion(auth=token)

    def create_page(self, db_id: str, properties: dict) -> str:
        page = self._c.pages.create(parent={"database_id": db_id}, properties=properties)
        return page["id"]

    def update_page(self, page_id: str, properties: dict) -> None:
        self._c.pages.update(page_id=page_id, properties=properties)
```

- [ ] **Step 2: Smoke-test against the real Notion DB** (one-off manual; needs the token from Task 0.1 + the Notes db id)

Run (replace the two values):
```bash
cd server/portfolio-api && ./.venv/bin/python -c "
from notion_kb import RealNotionClient
c = RealNotionClient('NOTION_TOKEN_HERE')
pid = c.create_page('NOTES_DB_ID_HERE', {'标题': {'title': [{'text': {'content': 'smoke test'}}]}, '情境': {'select': {'name': '自己想的'}}, '类型': {'select': {'name': '思考'}}})
print('created', pid)"
```
Expected: prints a page id; a "smoke test" row appears in the Notes DB. (Delete it after.) If a property name/type errors, fix the DB schema to match Task 0.1 exactly.

- [ ] **Step 3: Commit**
```bash
git add server/portfolio-api/notion_kb.py
git commit -m "feat(capture): RealNotionClient over notion-client SDK"
```

### Task 2.2: Postgres-backed KbIndex

**Files:** Modify `server/portfolio-api/notion_kb.py`

- [ ] **Step 1: Implement PgKbIndex** (uses the app's `_db()` contextmanager via a passed cursor factory to avoid import cycles — accept a `conn` per call)

Append to `notion_kb.py`:
```python
class PgKbIndex:
    """KbIndex backed by kb_concepts / kb_sources. Pass a live psycopg2 connection."""
    def __init__(self, conn):
        self.conn = conn

    def find_concept(self, user, name):
        with self.conn.cursor() as cur:
            cur.execute("SELECT notion_page_id, term_slug FROM kb_concepts WHERE username=%s AND lower(name)=lower(%s)",
                        (user, name.strip()))
            r = cur.fetchone()
            return {"page_id": r[0], "term_slug": r[1]} if r else None

    def add_concept(self, user, name, page_id, term_slug):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO kb_concepts (username, name, notion_page_id, term_slug) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT (username, lower(name)) DO NOTHING", (user, name.strip(), page_id, term_slug))

    def find_source(self, user, title):
        with self.conn.cursor() as cur:
            cur.execute("SELECT notion_page_id, canon_slug FROM kb_sources WHERE username=%s AND lower(title)=lower(%s)",
                        (user, title.strip()))
            r = cur.fetchone()
            return {"page_id": r[0], "canon_slug": r[1]} if r else None

    def add_source(self, user, title, page_id, canon_slug):
        with self.conn.cursor() as cur:
            cur.execute("INSERT INTO kb_sources (username, title, notion_page_id, canon_slug) VALUES (%s,%s,%s,%s) "
                        "ON CONFLICT (username, lower(title)) DO NOTHING", (user, title.strip(), page_id, canon_slug))
```

- [ ] **Step 2: Verify import**

Run: `cd server/portfolio-api && ./.venv/bin/python -c "import notion_kb; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**
```bash
git add server/portfolio-api/notion_kb.py
git commit -m "feat(capture): Postgres-backed KbIndex"
```

### Task 2.3: Notion token storage (reuse Fernet) + slug_lookup over glossary/canon

**Files:** Modify `server/portfolio-api/app.py`

- [ ] **Step 1: Add token store + a slug_lookup helper** (near the `_enc_secret`/`_dec_secret` and `glossary_terms`/`canon_items` code in `app.py`)
```python
def set_notion_token(user: str, token: str) -> None:
    with _db() as c, c.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS notion_tokens (
            username TEXT PRIMARY KEY, token_enc TEXT NOT NULL, updated_at TIMESTAMPTZ DEFAULT now())""")
        cur.execute("INSERT INTO notion_tokens (username, token_enc) VALUES (%s,%s) "
                    "ON CONFLICT (username) DO UPDATE SET token_enc=EXCLUDED.token_enc, updated_at=now()",
                    (user, _enc_secret(token)))

def get_notion_token(user: str) -> str | None:
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT token_enc FROM notion_tokens WHERE username=%s", (user,))
        r = cur.fetchone()
        return _dec_secret(r[0]) if r else None

def kb_slug_lookup(conn):
    """Returns slug_lookup(kind, key): concept name → glossary slug, source title → canon slug."""
    def lookup(kind: str, key: str):
        with conn.cursor() as cur:
            if kind == "concept":
                cur.execute("SELECT slug FROM glossary_terms WHERE lower(term)=lower(%s) LIMIT 1", (key,))
            else:
                cur.execute("SELECT slug FROM canon_items WHERE lower(title)=lower(%s) LIMIT 1", (key,))
            r = cur.fetchone()
            return r[0] if r else None
    return lookup
```

- [ ] **Step 2: Verify import**

Run: `cd server/portfolio-api && ./.venv/bin/python -c "import app; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**
```bash
git add server/portfolio-api/app.py
git commit -m "feat(capture): Fernet Notion-token store + glossary/canon slug lookup"
```

### Task 2.4: `do_capture` wiring + retry, persisting to `captures`

**Files:** Modify `server/portfolio-api/app.py`

- [ ] **Step 1: Add the prod entry that ties capture.py to PG + Notion + the buffer**
```python
import capture as _capture
import notion_kb as _nkb

_NOTION_DBS = {"notes": os.environ.get("VI_NOTION_DB_NOTES", ""),
               "concepts": os.environ.get("VI_NOTION_DB_CONCEPTS", ""),
               "sources": os.environ.get("VI_NOTION_DB_SOURCES", "")}

def do_capture(user: str, cap: dict) -> dict:
    """Persist a capture (buffer-first so it's never lost), then file into Notion."""
    with _db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO captures (username, raw, title, note_type, situation, tags) "
                    "VALUES (%s,%s,%s,%s,%s,%s) RETURNING id",
                    (user, cap.get("clean_content") or cap.get("raw", ""), cap.get("title"),
                     cap.get("note_type"), cap.get("situation"), json.dumps(cap.get("tags") or [])))
        cap_id = cur.fetchone()[0]
    token = get_notion_token(user)
    if not token:
        return {"ok": False, "error": "未连接 Notion", "capture_id": cap_id}
    try:
        with _db() as c:
            res = _capture.record_capture(_nkb.PgKbIndex(c), _nkb.RealNotionClient(token), user, cap,
                                          _NOTION_DBS, kb_slug_lookup(c), _now())
            with c.cursor() as cur:
                cur.execute("UPDATE captures SET status='written', notion_page_id=%s, written_at=now() WHERE id=%s",
                            (res["notion_page_id"], cap_id))
        return {"ok": True, "capture_id": cap_id, **res}
    except Exception as e:  # noqa: BLE001 — Notion down/limited: leave status=pending, retry later
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE captures SET status='pending', error=%s WHERE id=%s", (str(e)[:300], cap_id))
        return {"ok": False, "error": "Notion 写入失败，已缓冲稍后重试", "capture_id": cap_id}

def retry_pending_captures(user: str) -> int:
    """Re-file captures stuck in pending (Notion was down). Returns count re-filed."""
    token = get_notion_token(user)
    if not token:
        return 0
    n = 0
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT id, raw, title, note_type, situation, tags FROM captures "
                    "WHERE username=%s AND status='pending' ORDER BY id", (user,))
        rows = cur.fetchall()
    for rid, raw, title, ntype, situ, tags in rows:
        cap = {"clean_content": raw, "title": title, "note_type": ntype, "situation": situ,
               "tags": tags or [], "concepts": [], "source": None}
        try:
            with _db() as c:
                res = _capture.record_capture(_nkb.PgKbIndex(c), _nkb.RealNotionClient(token), user, cap,
                                              _NOTION_DBS, kb_slug_lookup(c), _now())
                with c.cursor() as cur:
                    cur.execute("UPDATE captures SET status='written', notion_page_id=%s, written_at=now() WHERE id=%s",
                                (res["notion_page_id"], rid))
            n += 1
        except Exception:  # noqa: BLE001 — still down, leave pending
            break
    return n
```

- [ ] **Step 2: Verify import**

Run: `cd server/portfolio-api && ./.venv/bin/python -c "import app; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**
```bash
git add server/portfolio-api/app.py
git commit -m "feat(capture): do_capture (buffer-first) + retry_pending_captures"
```

---

## Phase 3 — MCP tool, capture skill, hermes wiring

### Task 3.1: MCP server exposing capture_note

**Files:** Create `server/portfolio-api/mcp_server.py`

- [ ] **Step 1: Research the exact MCP server shape hermes expects.** Read `hermes mcp add --help` and `hermes mcp serve --help` on the server, and the MCP Python SDK (`mcp` package, `FastMCP`). Decide stdio command vs HTTP url. (Spec deferred this; pick `--command` stdio for a single-process tool.)

Run: `ssh openclaw 'hermes mcp add --help; echo ---; hermes mcp test --help'`

- [ ] **Step 2: Implement the MCP server wrapping `do_capture`** using `FastMCP` (install `mcp` in the venv if needed). Expose one tool `capture_note(payload: dict)` that calls `app.do_capture(user, payload)`. The `user` is derived from which profile's MCP this is (one MCP instance per tenant, or pass user in the payload — decide in Step 1).
```python
from mcp.server.fastmcp import FastMCP
import app as _app

mcp = FastMCP("vi-capture")

@mcp.tool()
def capture_note(user: str, title: str, clean_content: str, situation: str, note_type: str,
                 tags: list[str], concepts: list[dict], source: dict | None = None,
                 insight: str | None = None) -> dict:
    """File a knowledge capture into the user's Notion knowledge base. Returns a receipt."""
    return _app.do_capture(user, {
        "title": title, "clean_content": clean_content, "situation": situation,
        "note_type": note_type, "tags": tags, "concepts": concepts, "source": source, "insight": insight})

if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 3: Test the MCP server boots**

Run: `cd server/portfolio-api && ./.venv/bin/python mcp_server.py &` then `ssh`-side `hermes mcp test` once added. Expected: server starts; `hermes mcp test` lists `capture_note`.

- [ ] **Step 4: Commit**
```bash
git add server/portfolio-api/mcp_server.py
git commit -m "feat(capture): MCP server exposing capture_note"
```

### Task 3.2: The vi-capture-note skill

**Files:** Create `skills/vi-capture-note/SKILL.md`

- [ ] **Step 1: Write the skill** (mirror the format of `skills/vi-parse-holdings/SKILL.md`; frontmatter + body). The body instructs hermes: judge whether the message is worth keeping (a thought/takeaway/insight, NOT a plain question); if yes, call the `vi-capture:capture_note` tool with a structured payload; choose `situation`/`note_type`; only attach a `source` if it's a reusable, identifiable source; link existing concepts when possible (it may call `list_concepts`); never fabricate; produce a one-line `insight` only when there's a durable observation about the user.

```markdown
---
name: vi-capture-note
description: Capture a user's thought/insight into their Notion knowledge base via the capture_note tool.
---

# 随手沉淀技能

当用户在对话里抛出一个**值得留存**的想法/要点/洞察/疑问/反例(而不是单纯在问你一个问题),调用 `vi-capture:capture_note` 工具把它结构化归档。

## 何时调用
- 调用:用户分享一个观点、读/听到的要点、自己的疑问、一个反例、一个待办行动。
- 不调用:用户在问你问题、闲聊寒暄、让你执行别的任务。拿不准就**不记**(宁可漏,不要误记)。

## 怎么结构化 payload
- `title`:一句话摘要(≤20 字)。
- `clean_content`:用户原文,只做轻清洗(去口水,不改意思)。
- `situation`:`自己想的/闲聊/播客/书/文章/会议/其他` —— 这念头哪儿冒出来的。
- `note_type`:`思考/要点/疑问/反例/行动`。
- `tags`:2-4 个关键词。
- `concepts`:这条触及的耐久概念。先用 `vi-capture:list_concepts` 看已有的,命中就 `{"name":..., "existing":true}`,没有就 `{"name":..., "existing":false, "one_liner":"一句话定义"}`。链不上就给空数组。
- `source`:**仅当**有明确、可复用的来源(某本书/某档常听的播客/某封 letter)才给 `{"title","kind","author","url"}`;只是随口一个念头就给 `null`。
- `insight`:**仅当**这条透露出"这个用户是谁"的耐久观察(如"他总把波动当风险")才给一句;否则 `null`。

## 硬约束
- 绝不编造内容、数字、来源。
- 记完用一句话回执确认(工具返回的 receipt)。
```

- [ ] **Step 2: Seed it + distribute to profiles** (reuse existing pipeline)

Run (on the server / via the deploy path): `python seed.py` then `provision_hermes()` (or the existing endpoint that calls it) so `official_skills` gets the new row and each `app-*` profile gets the SKILL.md.

- [ ] **Step 3: Commit**
```bash
git add skills/vi-capture-note/SKILL.md
git commit -m "feat(capture): vi-capture-note skill"
```

### Task 3.3: Wire hermes — mcp add, SOUL, memory toolset

**Files:** none (server config; document the exact commands run)

- [ ] **Step 1: Add the capture MCP to each tenant profile**

Run per profile (e.g. app-lucas):
```bash
ssh openclaw 'hermes -p app-lucas mcp add vi-capture --command "/opt/value-investment-api/.venv/bin/python" --args "/opt/value-investment-api/mcp_server.py"'
```
(Adjust path to where the API is deployed. Confirm `--command/--args` syntax from Task 3.1 Step 1.) Verify: `hermes -p app-lucas mcp list` shows `vi-capture`; `hermes -p app-lucas tools list` shows `vi-capture:capture_note`.

- [ ] **Step 2: Add the capture trigger + memory guidance to each profile's SOUL**

Append to `~/.hermes/profiles/app-<user>/SOUL` (or via `hermes -p <user> config`): a short block — "当用户抛出值得留存的想法,用 vi-capture-note 技能归档;处理捕获与对话时,持续蒸馏并更新你对该用户的定性理解(他是谁、惯性误区、关注点),写入你的记忆。结构化事实(持仓/已读)不用记,系统会注入。"

- [ ] **Step 3: Enable the native memory toolset on the tenant profiles**

Run: `ssh openclaw 'hermes -p app-lucas tools enable memory'` (repeat per profile). Verify: `hermes -p app-lucas tools list | grep memory` shows enabled.

- [ ] **Step 4: End-to-end smoke** — message the Feishu bot (as lucas) with a real thought ("突然想到,把波动当风险是最常见的认知错误"). Expected: hermes replies with a receipt; a Note row appears in Notion linked to a 安全边际/风险 concept; `captures` row status=written.

- [ ] **Step 5: Commit a short ops runbook** capturing the exact commands used:
```bash
git add docs/superpowers/ # if you keep a runbook note
git commit -m "docs(capture): hermes wiring runbook (mcp add + SOUL + memory)"
```

---

## Phase 4 — Read-back (close the flywheel)

### Task 4.1: Mechanism A — inject recent-capture context (TDD)

**Files:** Modify `server/portfolio-api/app.py` (`_build_learner_profile`), Test `server/portfolio-api/tests/test_recent_context.py`

- [ ] **Step 1: Write the failing test** for a pure formatter that turns recent captures into a context string.

`server/portfolio-api/tests/test_recent_context.py`:
```python
from app import format_recent_context


def test_format_recent_context_lists_concepts_and_open_questions():
    rows = [
        {"title": "波动≠风险", "note_type": "思考", "concepts": ["安全边际"]},
        {"title": "DCF 真的可信吗", "note_type": "疑问", "concepts": ["DCF"]},
    ]
    s = format_recent_context(rows)
    assert "安全边际" in s
    assert "DCF 真的可信吗" in s        # open question surfaced
    assert "疑问" in s
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_recent_context.py -q`
Expected: FAIL — `format_recent_context` not defined.

- [ ] **Step 3: Implement the pure formatter + a loader, inject into the profile**

Add to `app.py`:
```python
def format_recent_context(rows: list[dict]) -> str:
    if not rows:
        return ""
    qs = [r["title"] for r in rows if r.get("note_type") == "疑问"]
    cons = sorted({c for r in rows for c in (r.get("concepts") or [])})
    parts = []
    if cons:
        parts.append("最近在记的概念：" + "、".join(cons[:12]))
    if qs:
        parts.append("未决疑问：" + "；".join(qs[:5]))
    return "【近期沉淀】" + " ".join(parts) if parts else ""
```
Then in `_build_learner_profile(user)`, query the last ~15 captures (join concept names) and add `profile["recent_context"] = format_recent_context(rows)`; include it in the prompt assembly where `mastered` etc. are injected.

- [ ] **Step 4: Run to verify it passes**

Run: `cd server/portfolio-api && ./.venv/bin/pytest tests/test_recent_context.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add server/portfolio-api/app.py server/portfolio-api/tests/test_recent_context.py
git commit -m "feat(capture): mechanism A — inject recent-capture context into hermes"
```

### Task 4.2: Mechanism B — verify native memory accumulates (config + verify)

**Files:** none (verification of Task 3.3's config)

- [ ] **Step 1: Have two short Feishu conversations** as lucas across "sessions" (separate `-z` calls / days), each revealing a durable trait (e.g. confuses 内在价值 vs 价格).
- [ ] **Step 2: Inspect the profile memory** wrote something: `ssh openclaw 'cat ~/.hermes/profiles/app-lucas/USER.md ~/.hermes/profiles/app-lucas/MEMORY.md 2>/dev/null'`. Expected: a qualitative line about lucas appears.
- [ ] **Step 3: If built-in memory is too thin/flat**, set up mem0: `ssh openclaw 'hermes -p app-lucas memory setup'` → pick mem0 → re-verify. (Decision deferred per spec; only escalate if needed.)
- [ ] **Step 4: Confirm the discipline** — grep the memory files do NOT contain structured holdings (e.g. no "持有 NVDA"). If they do, tighten the SOUL instruction. No commit (config/verify only).

---

## Self-Review

**Spec coverage:** Notion 3-DB model → Task 0.1 + mapping 1.2/1.4/1.5. hermes-self-decide + MCP → 3.1/3.2/3.3. Backend deterministic write + dedup + slug + Fernet token + PG buffer → 1.4–1.6, 2.1–2.4. Mechanism A → 4.1. Mechanism B (native memory, config) → 3.3 + 4.2. Connection via term_slug/canon_slug → 2.3 + 1.4/1.5. Error/retry/idempotency → 2.4. Testing → pytest throughout (1.x, 4.1). "不臃肿" (no app notes UI) → respected (no web UI task; the optional deep-link is left out as YAGNI). All success criteria 1–7 map to a task.

**Placeholder scan:** Integration tasks (3.1 Step 1, 3.3) intentionally include a "research exact hermes/MCP flags" step — these are the spec's explicitly-deferred items, with concrete verify commands, not vague placeholders. Pure-logic tasks have full code.

**Type consistency:** `find_or_create_concept`, `find_or_create_source`, `record_capture`, `map_note_properties`, `do_capture`, `retry_pending_captures`, `format_recent_context`, `PgKbIndex`/`FakeKbIndex` (find_/add_ concept/source), `RealNotionClient`/`FakeNotionClient` (create_page/update_page), `slug_lookup(kind, key)`, `db_ids` keys `{notes,concepts,sources}` — names are consistent across all tasks.

**Open dependency:** Phase 3 requires the API + venv deployed at a known server path (`/opt/value-investment-api/`); confirm the actual deploy path before Task 3.3.
