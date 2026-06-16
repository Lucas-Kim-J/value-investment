import json
import pytest

from content_pipeline.models import ContentItem
from content_pipeline.distiller import build_distill_input, parse_signal_card, Distiller


def _item():
    return ContentItem(source="xiaoyuzhou", external_id="e1", title="Ep 9 | 测试",
                       url="u", published_at="p", is_paid=False, media_url="m")


def _valid_card():
    return {"tldr": "主旨", "non_consensus": "他认为X而共识Y", "new_angle": "迁移角度",
            "pillar": "资金传导", "caution": "他重crypto，注意利益相关",
            "worth_relisten": {"yes": True, "timestamps": ["12:30 关于X"]}}


def test_build_input_includes_title_and_transcript_and_pillars():
    s = build_distill_input(_item(), "这是转录全文。")
    assert "Ep 9 | 测试" in s
    assert "这是转录全文。" in s
    assert "第一性原理" in s and "资金传导" in s and "历史镜像" in s


def test_build_input_uses_show_title_when_present():
    it = ContentItem(source="xiaoyuzhou", external_id="e1", title="t", url="u",
                     published_at="p", is_paid=False, media_url="m",
                     show_title="The Wanderers 流浪者")
    assert "The Wanderers 流浪者" in build_distill_input(it, "转录")


def test_fit_transcript_keeps_short_unchanged():
    from content_pipeline.distiller import _fit_transcript
    s = "短转录内容" * 50
    assert _fit_transcript(s) == s


def test_fit_transcript_trims_oversized_to_head_tail_with_marker():
    from content_pipeline.distiller import _fit_transcript, _MAX_TRANSCRIPT_BYTES
    big = "字" * 200_000                      # ~600KB utf-8 (a 4–7h episode)
    out = _fit_transcript(big)
    assert len(out.encode("utf-8")) <= _MAX_TRANSCRIPT_BYTES + 200   # fits the argv budget
    assert "省略" in out                       # elision marker present
    assert out.startswith("字") and out.rstrip().endswith("字")       # head + tail kept


def test_build_input_caps_oversized_transcript_under_arg_limit():
    from content_pipeline.distiller import _MAX_TRANSCRIPT_BYTES
    it = ContentItem(source="xiaoyuzhou", external_id="e1", title="t", url="u",
                     published_at="p", is_paid=False, media_url="m", show_title="X")
    s = build_distill_input(it, "字" * 200_000)
    assert len(s.encode("utf-8")) <= _MAX_TRANSCRIPT_BYTES + 4000     # whole prompt stays safe


def test_parse_signal_card_accepts_plain_json():
    card = parse_signal_card(json.dumps(_valid_card(), ensure_ascii=False))
    assert card["pillar"] == "资金传导"
    assert card["worth_relisten"]["yes"] is True


def test_parse_signal_card_extracts_from_fenced_block():
    raw = "好的，结果如下：\n```json\n" + json.dumps(_valid_card(), ensure_ascii=False) + "\n```\n"
    card = parse_signal_card(raw)
    assert card["tldr"] == "主旨"


def test_parse_signal_card_rejects_missing_key():
    bad = _valid_card(); del bad["caution"]
    with pytest.raises(ValueError):
        parse_signal_card(json.dumps(bad, ensure_ascii=False))


def test_parse_signal_card_rejects_bad_pillar():
    bad = _valid_card(); bad["pillar"] = "玄学"
    with pytest.raises(ValueError):
        parse_signal_card(json.dumps(bad, ensure_ascii=False))


def test_parse_signal_card_ignores_trailing_prose_with_braces():
    # hermes returns a valid card then stray prose containing a '}' — the
    # first complete object must still parse (regression: greedy {.*} over-captured).
    raw = json.dumps(_valid_card(), ensure_ascii=False) + "\n注意：仅供参考 {补充说明}。"
    card = parse_signal_card(raw)
    assert card["pillar"] == "资金传导"


def test_parse_signal_card_handles_leading_prose_then_object():
    raw = "结果如下：" + json.dumps(_valid_card(), ensure_ascii=False)
    card = parse_signal_card(raw)
    assert card["tldr"] == "主旨"


def test_parse_signal_card_rejects_non_json():
    with pytest.raises(ValueError):
        parse_signal_card("我没有返回 json")


def test_distill_calls_runner_and_parses():
    captured = {}

    def fake_runner(prompt):
        captured["prompt"] = prompt
        return json.dumps(_valid_card(), ensure_ascii=False)

    card = Distiller(runner=fake_runner).distill(_item(), "转录")
    assert "转录" in captured["prompt"]
    assert card["pillar"] == "资金传导"
