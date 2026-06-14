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
