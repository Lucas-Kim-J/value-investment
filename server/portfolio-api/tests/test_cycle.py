"""Unit tests for cycle.py — pure market-cycle scoring."""
import cycle


def test_recession_prob_monotonic_and_bounded():
    # deeper inversion → higher recession probability; positive spread → low
    p_inverted = cycle.recession_prob_from_curve(-1.0)
    p_flat = cycle.recession_prob_from_curve(0.0)
    p_steep = cycle.recession_prob_from_curve(2.0)
    assert 0 < p_steep < p_flat < p_inverted < 1
    assert cycle.recession_prob_from_curve(None) is None


def test_yield_curve_lens_bands():
    assert cycle.yield_curve_lens(2.0)[0] == 2        # steep → early cycle
    assert cycle.yield_curve_lens(0.8)[0] == 1
    assert cycle.yield_curve_lens(0.2)[0] == 0
    assert cycle.yield_curve_lens(-0.2)[0] == -1      # inverted
    assert cycle.yield_curve_lens(-1.5)[0] == -2      # deep inversion → high recession prob
    assert cycle.yield_curve_lens(None) is None


def test_valuation_lens_is_inverse():
    assert cycle.valuation_lens(10)[0] == 2           # cheap → supportive
    assert cycle.valuation_lens(50)[0] == 0
    assert cycle.valuation_lens(80)[0] == -1
    assert cycle.valuation_lens(97, cape=42.2)[0] == -2   # expensive → caps returns
    assert cycle.valuation_lens(None) is None


def test_volatility_lens_term_structure():
    assert cycle.volatility_lens(0.80)[0] == 1        # healthy contango
    assert cycle.volatility_lens(0.90)[0] == 0
    assert cycle.volatility_lens(0.98)[0] == -1
    assert cycle.volatility_lens(1.10)[0] == -2       # backwardation = fear
    assert cycle.volatility_lens(None) is None


def test_credit_lens_low_spread_is_risk_on():
    assert cycle.credit_lens(8)[0] == 2               # tight spread → loose credit
    assert cycle.credit_lens(40)[0] == 1
    assert cycle.credit_lens(60)[0] == -1
    assert cycle.credit_lens(90)[0] == -2             # blown out → stress
    assert cycle.credit_lens(None) is None


def test_liquidity_lens_combines_slope_and_m2():
    assert cycle.liquidity_lens(1.2, 4.5)[0] == 2     # both expanding
    assert cycle.liquidity_lens(-1.0, -2.0)[0] == -2  # both contracting
    assert cycle.liquidity_lens(1.0, -1.0)[0] == 0    # mixed
    assert cycle.liquidity_lens(None, None) is None


def test_cape_discount_flag_trips_above_90th():
    flagged, note = cycle.cape_discount_flag(97)
    assert flagged and "回报" in note
    assert cycle.cape_discount_flag(60) == (False, "")
    assert cycle.cape_discount_flag(None) == (False, "")


def test_composite_risk_on_when_lenses_positive():
    lenses = {
        "yield_curve": cycle.yield_curve_lens(1.0),
        "credit": cycle.credit_lens(10),
        "liquidity": cycle.liquidity_lens(1.0, 4.0),
        "valuation": cycle.valuation_lens(40),
        "volatility": cycle.volatility_lens(0.85),
    }
    out = cycle.composite_cycle(lenses)
    assert out["level"] >= 4 and out["tailwind"] == "顺风"
    assert out["lenses_missing"] == []


def test_composite_sahm_breaker_forces_recession():
    lenses = {"credit": cycle.credit_lens(10), "liquidity": cycle.liquidity_lens(2.0, 5.0)}
    out = cycle.composite_cycle(lenses, sahm=0.6)
    assert out["sahm_breaker"] is True
    assert out["level"] == 1 and out["tailwind"] == "逆风"


def test_composite_handles_missing_lenses_gracefully():
    # only the keyless core present (no FRED credit/liquidity)
    lenses = {"yield_curve": cycle.yield_curve_lens(-0.3), "valuation": cycle.valuation_lens(97),
              "volatility": cycle.volatility_lens(0.86)}
    out = cycle.composite_cycle(lenses)
    assert out["score"] is not None
    assert set(out["lenses_missing"]) == {"credit", "liquidity"}


def test_valuation_excluded_from_regime_blend_but_caps_returns():
    # expensive market + strong credit/liquidity = risk-ON regime (valuation does NOT
    # drag the regime), but the return-cap flag is up. This is the 2026-ish shape.
    lenses = {"yield_curve": cycle.yield_curve_lens(0.5), "valuation": cycle.valuation_lens(97),
              "volatility": cycle.volatility_lens(0.86), "credit": cycle.credit_lens(8),
              "liquidity": cycle.liquidity_lens(1.0, 4.5)}
    out = cycle.composite_cycle(lenses)
    assert out["level"] >= 4                       # regime is risk-on (valuation excluded)
    assert "valuation" not in out["lenses_missing"]  # it's just not a regime lens
    assert cycle.cape_discount_flag(97)[0]         # …but returns are capped


def test_asset_tilt_shape():
    t = cycle.asset_tilt(1)
    assert t["现金"] == "✓" and t["成长股"] == "✕"   # risk-off favors cash, shuns growth
    t5 = cycle.asset_tilt(5)
    assert t5["成长股"] == "✓" and t5["现金"] == "✕"


def test_value_cycle_overlay_matrix():
    cheap_head = cycle.value_cycle_overlay("便宜", "逆风")
    assert "小仓" in cheap_head["stance"]          # cheap but headwind → small/patient
    rich_head = cycle.value_cycle_overlay("贵", "逆风")
    assert "清仓" in rich_head["stance"] or "对冲" in rich_head["stance"]
    cheap_tail = cycle.value_cycle_overlay("便宜", "顺风")
    assert "重仓" in cheap_tail["stance"]
    assert cycle.value_cycle_overlay("便宜", None) is None
    assert cycle.value_cycle_overlay(None, "顺风") is None
