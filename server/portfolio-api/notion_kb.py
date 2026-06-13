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
