"""Unit tests for the macro capital-transmission scoring (pure, no network)."""
import macro as m


def test_rate_trend():
    assert m.rate_trend(4.5, 3.0) == "上行"
    assert m.rate_trend(2.0, 4.0) == "下行"
    assert m.rate_trend(4.5, 4.4) == "持平"
    assert m.rate_trend(None, 3.0) is None


def test_curve_state():
    assert m.curve_state(-0.3) == "倒挂"
    assert m.curve_state(0.2) == "平坦"
    assert m.curve_state(1.5) == "正常"
    assert m.curve_state(None) is None


def test_sensitivity_high_when_levered_uncovered_longduration():
    s = m.sensitivity(d2e=200, interest_coverage=2, pe=40, growth=30)
    assert s["score"] == "高" and len(s["drivers"]) >= 3


def test_sensitivity_low_for_defensive():
    s = m.sensitivity(d2e=20, interest_coverage=30, pe=12)
    assert s["score"] == "低"


def test_sensitivity_insufficient_data():
    assert m.sensitivity()["score"] == "数据不足"


def test_assemble_note_mentions_env_and_company():
    env = {"ten_year": 4.49, "rate_trend": "上行", "curve_state": "倒挂"}
    out = m.assemble(env, d2e=180, interest_coverage=3, pe=38, market="美股")
    assert out["sensitivity"]["score"] == "高"
    assert "10Y" in out["note"] and "倒挂" in out["note"] and "逆风" in out["note"]


def test_assemble_cn_includes_lpr():
    env = {"ten_year": 1.74, "lpr_1y": 3.0, "curve_state": "正常"}
    out = m.assemble(env, d2e=20, pe=19, market="A股")
    assert "LPR" in out["note"]
