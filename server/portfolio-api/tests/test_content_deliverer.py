from content_pipeline.models import ContentItem
from content_pipeline.deliverer import render_new_notice, render_signal_card, Deliverer


def _item(paid=False, show_title=None):
    return ContentItem(source="xiaoyuzhou", external_id="e1", title="Ep 9 | 测试",
                       url="https://x/episode/e1", published_at="p",
                       is_paid=paid, media_url="m", show_title=show_title)


def _card():
    return {"tldr": "主旨", "non_consensus": "他X共识Y", "new_angle": "迁移角度",
            "pillar": "资金传导", "caution": "注意利益相关",
            "worth_relisten": {"yes": True, "timestamps": ["12:30 关于X"]}}


def test_render_new_notice_has_title_and_link():
    s = render_new_notice(_item())
    assert "Ep 9 | 测试" in s
    assert "https://x/episode/e1" in s


def test_render_new_notice_paid_marks_paid():
    s = render_new_notice(_item(paid=True))
    assert "付费" in s


def test_render_signal_card_has_all_fields():
    s = render_signal_card(_item(), _card())
    for piece in ["主旨", "他X共识Y", "迁移角度", "资金传导", "注意利益相关", "12:30"]:
        assert piece in s


def test_render_signal_card_includes_signals_deeplink():
    s = render_signal_card(_item(), _card())
    assert "/signals" in s          # deep link back to the website's 信号 page
    assert "在网站看" in s


def test_deliverer_send_new_notice_calls_runner():
    sent = []
    d = Deliverer(runner=lambda text, subject: sent.append((subject, text)))
    d.send_new_notice(_item())
    assert len(sent) == 1
    assert "Ep 9 | 测试" in sent[0][1]


def test_deliverer_send_signal_card_calls_runner():
    sent = []
    d = Deliverer(runner=lambda text, subject: sent.append((subject, text)))
    d.send_signal_card(_item(), _card())
    assert "资金传导" in sent[0][1]


def test_render_uses_show_title_when_present():
    it = _item(show_title="张小珺Jùn｜商业访谈录")
    assert "张小珺" in render_new_notice(it)
    assert "张小珺" in render_signal_card(it, _card())


def test_render_falls_back_to_default_show_when_missing():
    # show_title=None → keeps the original 非共识的20分钟 label
    assert "非共识的20分钟" in render_new_notice(_item())
    assert "非共识的20分钟" in render_signal_card(_item(), _card())


def test_deliverer_subject_carries_show_title():
    sent = []
    d = Deliverer(runner=lambda text, subject: sent.append((subject, text)))
    it = _item(show_title="The Wanderers 流浪者")
    d.send_new_notice(it)
    d.send_signal_card(it, _card())
    assert "The Wanderers 流浪者" in sent[0][0]   # 新集 subject
    assert "The Wanderers 流浪者" in sent[1][0]   # 信号卡 subject
