"""Unit tests for board.py — pure market-board scoring."""
import board


def test_valuation_gauge_blends_and_bands():
    assert board.valuation_gauge(95, 99)["level"] == 4        # extreme → 极贵
    assert "天花板" in board.valuation_gauge(95, 99)["note"]
    assert board.valuation_gauge(50, None)["level"] == 2      # neutral, one source
    assert board.valuation_gauge(10, 20)["label"] == "便宜"
    assert board.valuation_gauge(None, None)["level"] is None  # no data


def test_breadth_gauge_bands():
    assert board.breadth_gauge(80, 75)["level"] == 4 and board.breadth_gauge(80, 75)["healthy"]
    assert board.breadth_gauge(55, 60)["level"] == 3
    assert board.breadth_gauge(40, 45)["healthy"] is False
    assert board.breadth_gauge(20, 25)["level"] == 1
    assert board.breadth_gauge(None, None)["level"] is None


def test_concentration_gauge_flags_narrow_leadership():
    g = board.concentration_gauge(35, 850, 10)               # heavy top-7 + low equal/cap pctile
    assert g["concentrated"] is True and "集中" in g["label"]
    assert "前7大权重 35%" in g["detail"]
    g2 = board.concentration_gauge(22, 500, 60)              # spread out
    assert g2["concentrated"] is False
    assert board.concentration_gauge(None, None, None)["label"] == "数据缺失"


def test_herfindahl():
    assert board.herfindahl([10, 10, 10]) == 300.0           # 3×100
    assert board.herfindahl([]) is None


def test_sector_heat_quadrants():
    assert board.sector_heat(0.2, 0.1)["quadrant"] == "领先"    # both positive
    assert board.sector_heat(0.2, -0.1)["quadrant"] == "转弱"   # was strong, fading
    assert board.sector_heat(-0.2, -0.1)["quadrant"] == "落后"  # both negative
    assert board.sector_heat(-0.2, 0.1)["quadrant"] == "改善"   # turning up
    h = board.sector_heat(0.43, 0.21)                          # SMH-like
    assert h["heat"] == 32.0 and h["rs_6m"] == 43.0
    assert board.sector_heat(None, 0.1)["heat"] is None


def test_market_temperature_hot_when_expensive_and_weak_breadth():
    val = board.valuation_gauge(97, 99)        # 极贵
    bre = board.breadth_gauge(35, 40)          # 偏弱 (not healthy)
    con = board.concentration_gauge(35, 900, 10)
    t = board.market_temperature(val, bre, con)
    assert t["hot"] is True and t["concentrated"] is True
