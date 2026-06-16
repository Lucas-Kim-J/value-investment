"""Unit tests for rates.py — pure 利率与央行 scoring."""
import rates


def test_implied_path_below_policy_is_cuts():
    p = rates.implied_path(3.2, 3.75, 3.5)
    assert p["direction"] == "降息" and "降息" in p["note"]


def test_implied_path_above_policy_is_not_cutting():
    # the live 2026 shape: 2Y 4.09 above the 3.50–3.75 band
    p = rates.implied_path(4.09, 3.75, 3.5)
    assert p["direction"].startswith("偏紧") and p["gap_bps"] > 0


def test_implied_path_near_policy_is_flat():
    assert rates.implied_path(3.70, 3.75, 3.5)["direction"] == "持平"
    assert rates.implied_path(None, 3.75) is None


def test_dot_plot_path_and_direction():
    d = rates.dot_plot([(2026, 3.4), (2027, 3.1), (2028, 3.1)], current_mid=3.625)
    assert d["direction"] == "降息"
    assert "3.40%" in d["note"] and "3.10%" in d["note"]
    assert rates.dot_plot([], 3.6) is None


def test_path_comparison_flags_divergence():
    # market not cutting + Fed cutting → market more hawkish (the live signal)
    assert "更鹰" in rates.path_comparison("偏紧 / 不降息", "降息")
    # market cutting + Fed holding → market more dovish
    assert "更鸽" in rates.path_comparison("降息", "持平")
    # aligned
    assert "一致" in rates.path_comparison("降息", "降息")
    assert rates.path_comparison(None, "降息") == ""


def test_yoy():
    assert rates.yoy(333.979, 320.302) == 4.3
    assert rates.yoy(100, 0) is None
    assert rates.yoy(None, 100) is None


def test_trend_labels():
    assert rates.trend(4.3, 3.9, rising="上升", falling="下降") == "上升"
    assert rates.trend(3.5, 4.3, rising="升温", falling="降温") == "降温"
    assert rates.trend(4.0, 4.05, rising="升", falling="降") == "持平"
    assert rates.trend(None, 4.0, rising="升", falling="降") is None
