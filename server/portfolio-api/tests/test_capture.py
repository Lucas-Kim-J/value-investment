from capture import map_note_properties


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
