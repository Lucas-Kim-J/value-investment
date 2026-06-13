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
