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
