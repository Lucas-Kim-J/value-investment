from app import format_recent_context


def test_format_recent_context_lists_concepts_and_open_questions():
    rows = [
        {"title": "波动≠风险", "note_type": "思考", "concepts": ["安全边际"]},
        {"title": "DCF 真的可信吗", "note_type": "疑问", "concepts": ["DCF"]},
    ]
    s = format_recent_context(rows)
    assert "安全边际" in s
    assert "DCF 真的可信吗" in s        # open question surfaced
    assert "疑问" in s
