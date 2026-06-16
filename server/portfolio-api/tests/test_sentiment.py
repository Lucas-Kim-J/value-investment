"""Unit tests for sentiment.py — pure 情绪 scoring."""
import sentiment


def test_fg_gauge_bands_and_contrarian():
    assert sentiment.fg_gauge(10)["level"] == 1 and "偏多" in sentiment.fg_gauge(10)["contrarian"]
    assert sentiment.fg_gauge(40)["label"] == "恐惧"
    assert sentiment.fg_gauge(50)["label"] == "中性"
    assert sentiment.fg_gauge(65)["label"] == "贪婪"
    assert sentiment.fg_gauge(85)["level"] == 5 and "偏空" in sentiment.fg_gauge(85)["contrarian"]
    assert sentiment.fg_gauge(None)["level"] is None


def test_composite_blends_fg_and_vix():
    fg = sentiment.fg_gauge(40)
    c = sentiment.composite(fg, (0, "波动率 contango（温和）", "VIX/VIX3M=0.86"))
    assert "恐惧贪婪 恐惧(40)" in c["label"]
    assert "波动率" in c["label"]


def test_composite_handles_missing():
    assert sentiment.composite(None, None)["label"] == "数据缺失"
