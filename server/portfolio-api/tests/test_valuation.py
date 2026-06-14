"""Unit tests for the valuation-consensus signal engine (pure, no network)."""
import valuation as v


def test_cagr():
    assert v._cagr([100, 110, 121]) == 0.1          # 10%/yr
    assert v._cagr([100]) is None                    # need ≥2 points
    assert v._cagr([None, 100, 0, 200]) == 1.0       # drops None/non-positive → 100→200 over 1 step
    assert v._cagr(None) is None


def test_reverse_dcf_monotonic_and_bounds():
    # price below PV even at the -50% floor → pins to the low bound
    assert v.reverse_dcf_growth(1000, 500) == -0.5
    # OE == MV (P/OE = 1) is extremely cheap → deeply negative implied growth (real root)
    assert v.reverse_dcf_growth(1000, 1000) < -0.4
    # an absurdly expensive case (tiny OE vs huge price) → pins to the high bound
    assert v.reverse_dcf_growth(1, 1e9) == 1.0
    # invalid inputs
    assert v.reverse_dcf_growth(-5, 100) is None
    assert v.reverse_dcf_growth(100, 0) is None
    # higher price ⇒ higher implied growth (monotonic)
    g_cheap = v.reverse_dcf_growth(100, 1500)
    g_dear = v.reverse_dcf_growth(100, 3000)
    assert g_cheap is not None and g_dear is not None and g_dear > g_cheap


def _verdict(tools, key):
    return next(t["verdict"] for t in tools if t["key"] == key)


def test_signals_cheap_company_triggers_deep_research():
    # cheap: low implied growth vs history, low P/E percentile, high OE-yield spread
    s = v.signals(
        market_cap=1000.0, owner_earnings=80.0, net_debt=-50.0, ebit=120.0,
        pe_percentile=5, ten_year_yield=0.02, hist_rev_cagr=0.12, hist_eps_cagr=0.12,
    )
    assert _verdict(s["tools"], "hist_pe") == "便宜"
    assert _verdict(s["tools"], "oe_yield") == "便宜"        # 8% - 2% = +6% ≥ +4%
    assert _verdict(s["tools"], "reverse_dcf") == "便宜"     # implied < hist 12%
    assert _verdict(s["tools"], "ev_ebit") == "待同行"
    assert s["cheap_count"] >= 2 and s["deep_research"] is True
    assert s["ev_ebit"] == round((1000 - 50) / 120, 1)


def test_signals_expensive_company():
    s = v.signals(
        market_cap=1e12, owner_earnings=1e10, net_debt=0, ebit=2e10,
        pe_percentile=95, ten_year_yield=0.045, hist_rev_cagr=0.02, hist_eps_cagr=0.03,
    )
    assert _verdict(s["tools"], "hist_pe") == "偏贵"
    assert _verdict(s["tools"], "oe_yield") == "偏贵"        # 1% - 4.5% < 0
    assert _verdict(s["tools"], "reverse_dcf") == "偏贵"     # implied ≫ hist
    assert s["cheap_count"] == 0 and s["deep_research"] is False


def test_signals_missing_data_is_graceful():
    s = v.signals(
        market_cap=None, owner_earnings=None, net_debt=None, ebit=None,
        pe_percentile=None, ten_year_yield=None,
    )
    assert all(t["verdict"] in ("数据缺失", "待同行") for t in s["tools"])
    assert s["cheap_count"] == 0 and s["deep_research"] is False
