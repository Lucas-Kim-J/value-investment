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
