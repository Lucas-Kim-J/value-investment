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
