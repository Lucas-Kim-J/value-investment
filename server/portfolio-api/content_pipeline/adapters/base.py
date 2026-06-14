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
