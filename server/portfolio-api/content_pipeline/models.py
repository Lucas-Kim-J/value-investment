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
