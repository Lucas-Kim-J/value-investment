"""Unit tests for the earnings-quality / capital-transmission forensics engine."""
import forensics as fx


def test_cash_conversion_verdicts():
    high = fx.cash_conversion([100, 110, 120], [95, 105, 118])
    assert high["cum_fcf_ni"] >= 0.8 and "高" in high["verdict"]
    low = fx.cash_conversion([100, 100, 100], [30, 20, 10])
    assert low["cum_fcf_ni"] < 0.5 and "纸面利润" in low["verdict"]
    assert fx.cash_conversion([], []) is None


def test_accruals_flags_receivables_outgrowing_revenue():
    a = fx.accruals(revenue=[100, 105, 110], receivables=[20, 30, 45], inventory=[10, 10, 11])
    assert a["recv_flag"] is True          # receivables CAGR ≫ revenue CAGR
    assert a["inv_flag"] is False
    clean = fx.accruals(revenue=[100, 120, 140], receivables=[20, 22, 24], inventory=[10, 11, 12])
    assert clean["recv_flag"] is False


def test_incremental_roic_detects_deterioration():
    # EBIT grows little while invested capital balloons → incremental ROIC ≪ average
    d = fx.incremental_roic(ebit=[100, 105, 108], invested_capital=[200, 400, 800])
    assert d["incremental"] < d["avg_roic"] and "衰减" in d["verdict"]
    # too few points
    assert fx.incremental_roic([100, 110], [200, 220]) is None


def test_signals_red_flags_and_count():
    s = fx.signals(
        net_income=[100, 100, 100], revenue=[100, 105, 110],
        fcf=[40, 35, 30],                                  # cum 0.35 → cash flag
        ebit=[50, 52, 54], invested_capital=[100, 300, 600],  # incremental ROIC decay
        receivables=[10, 20, 35], inventory=[10, 10, 11],   # receivables flag
        goodwill_latest=80, equity_latest=100,              # goodwill 80% → flag
        payout_ratio=1.3,                                   # 130% payout → flag
    )
    hits = {f["name"]: f["hit"] for f in s["red_flags"]}
    assert hits["经营现金流长期<净利润"] is True
    assert hits["应收增速>营收增速"] is True
    assert hits["商誉占净资产>30%"] is True
    assert hits["派息>盈利(>100%)"] is True
    assert hits["增量ROIC衰减"] is True
    assert s["flag_count"] == 5
    assert s["goodwill_ratio"] == 80.0 and s["payout_ratio"] == 130.0


def test_signals_clean_company_no_flags():
    s = fx.signals(
        net_income=[100, 110, 120], revenue=[100, 120, 140],
        fcf=[100, 110, 125], ebit=[50, 70, 95], invested_capital=[200, 240, 290],
        receivables=[20, 23, 26], inventory=[10, 11, 12],
        goodwill_latest=5, equity_latest=100, payout_ratio=0.3,
    )
    assert s["flag_count"] == 0


def test_signals_missing_inputs_graceful():
    s = fx.signals(net_income=[100, 110], fcf=[90, 100])
    assert s["cash_conversion"] is not None
    assert s["accruals"] is None and s["incremental_roic"] is None
    assert s["flag_count"] == 0
