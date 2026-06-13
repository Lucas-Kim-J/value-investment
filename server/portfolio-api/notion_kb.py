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


class KbIndex(Protocol):
    def find_concept(self, user: str, name: str) -> dict | None: ...
    def add_concept(self, user: str, name: str, page_id: str, term_slug: str | None) -> None: ...
    def find_source(self, user: str, title: str) -> dict | None: ...
    def add_source(self, user: str, title: str, page_id: str, canon_slug: str | None) -> None: ...


from notion_client import Client as _Notion


class RealNotionClient:
    def __init__(self, token: str):
        self._c = _Notion(auth=token)

    def create_page(self, db_id: str, properties: dict) -> str:
        page = self._c.pages.create(parent={"database_id": db_id}, properties=properties)
        return page["id"]

    def update_page(self, page_id: str, properties: dict) -> None:
        self._c.pages.update(page_id=page_id, properties=properties)


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
