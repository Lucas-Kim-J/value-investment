from capture import map_note_properties
from capture import find_or_create_concept
from capture import find_or_create_source


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


def test_find_or_create_source_dedupes_by_title(notion, kb):
    src = {"title": "纵横四海 EP100", "kind": "播客", "author": "劲波", "url": "https://x"}
    sid1 = find_or_create_source(kb, notion, "lucas", src, sources_db_id="DBS", canon_slug=None)
    sid2 = find_or_create_source(kb, notion, "lucas", {"title": "纵横四海 EP100"}, sources_db_id="DBS", canon_slug=None)
    assert sid1 == sid2
