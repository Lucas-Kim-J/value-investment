"""Unit tests for the pure (no-network) helpers in market_data.

The network-backed functions (snapshot/news/sec_filings) are smoke-tested
manually against live sources; here we lock down the parsing + scoring logic
that turns raw vendor data into the dashboard shape.
"""
import market_data as md


def test_num_coerces_nan_inf_and_junk_to_none():
    assert md._num(3) == 3.0
    assert md._num("4.5") == 4.5
    assert md._num(None) is None
    assert md._num(float("nan")) is None
    assert md._num(float("inf")) is None
    assert md._num("not-a-number") is None


def test_pct_scales_decimals_to_percent():
    assert md._pct(0.2715) == 27.15
    assert md._pct(0) == 0.0
    assert md._pct(None) is None


def test_band_ascending_and_missing():
    bands = [(10, 90), (20, 65), (1e9, 20)]
    assert md._band(8, bands) == 90       # <=10
    assert md._band(15, bands) == 65      # <=20
    assert md._band(500, bands) == 20     # catch-all
    assert md._band(None, bands) is None  # missing metric → no score


def test_ratio_series_handles_zero_and_none_denominator():
    assert md._ratio_series([50, 30, 20], [100, 0, None]) == [50.0, None, None]
    assert md._ratio_series(None, [1, 2]) is None


def test_radar_shape_and_missing_axis():
    # cheap, profitable, no balance-sheet data → health axis should be None
    metrics = {
        "pe": 9, "pb": 0.9, "net_margin": 22, "roe": 26,
        "revenue_growth": 14, "earnings_growth": 25,
        "debt_to_equity": None, "current_ratio": None,
    }
    fin = {"revenue": [100, 120], "fcf": [12, 18]}
    r = md._radar(metrics, fin)
    names = [i["name"] for i in r["indicators"]]
    assert names == ["估值", "盈利能力", "成长", "财务健康", "现金流"]
    assert len(r["values"]) == 5
    assert r["values"][0] >= 80          # cheap → high value score
    assert r["values"][3] is None        # no balance-sheet data → missing
    assert "估值" in r["notes"]


def test_norm_time_epoch_and_iso():
    assert md._norm_time(0).startswith("1970-01-01")
    assert md._norm_time(None) is None
    # RFC822 (Google News) parses to ISO
    assert md._norm_time("Fri, 13 Jun 2026 20:08:31 GMT").startswith("2026-06-13")


def test_is_us_market_classifier():
    assert md._is_us("美股") and md._is_us("") and md._is_us("US")
    assert not md._is_us("A股") and not md._is_us("港股") and not md._is_us("加密")


def test_is_cn_market_classifier():
    assert md._is_cn("A股") and md._is_cn("沪深京") and md._is_cn("CN")
    assert not md._is_cn("美股") and not md._is_cn("港股")


def test_cn_code_normalizes_ticker_forms():
    assert md._cn_code("600519") == "600519"
    assert md._cn_code("sh600519") == "600519"
    assert md._cn_code("600519.SS") == "600519"
    assert md._cn_code("000001.SZ") == "000001"


def test_cn_prefix_by_board():
    assert md._cn_prefix("600519") == "sh"
    assert md._cn_prefix("000001") == "sz" and md._cn_prefix("300750") == "sz"
    assert md._cn_prefix("830799") == "bj"


def test_cn_form_classifies_announcements():
    assert md._cn_form("贵州茅台2025年年度报告") == "年报"
    assert md._cn_form("xx2025年半年度报告") == "中报"
    assert md._cn_form("xx第三季度报告") == "三季报"
    assert md._cn_form("关于职工董事选举结果的公告") == "公告"


def test_price_dict_shape():
    rows = [("2021-01", 10, 12, 9, 13), ("2021-02", 12, 11, 10, 14)]
    d = md._price_dict(rows)
    assert d["dates"] == ["2021-01", "2021-02"]
    assert d["ohlc"][0] == [10, 12, 9, 13]   # open, close, low, high
    assert d["close"] == [12, 11]


def test_by_year_keeps_positive_only():
    assert md._by_year([("2023", 5), ("2024", 0), ("2025", -3), ("2026", 7)]) == {"2023": 5.0, "2026": 7.0}


def test_val_for_year_exact_prior_earliest():
    by = {"2022": 4.0, "2024": 6.0}
    assert md._val_for_year("2022", by) == 4.0      # exact
    assert md._val_for_year("2025", by) == 6.0      # most-recent prior
    assert md._val_for_year("2020", by) == 4.0      # earliest available
    assert md._val_for_year("2024", {}) is None


def test_percentile_cheap_vs_dear():
    hist = list(range(1, 101))                       # 1..100
    assert md._percentile(hist, 2) <= 3              # near the cheap end
    assert md._percentile(hist, 99) >= 98            # near the dear end
    assert md._percentile(hist, 50) is not None
    assert md._percentile([1, 2, 3], 2) is None      # <30 points → not meaningful


def test_peer_metrics_extracts_and_computes_ev_ebitda():
    info = {"marketCap": 1e9, "trailingPE": 20, "returnOnEquity": 0.25,
            "grossMargins": 0.6, "profitMargins": 0.2, "enterpriseValue": 1.2e9, "ebitda": 1e8}
    m = md._peer_metrics(info, "XYZ")
    assert m["ticker"] == "XYZ" and m["pe"] == 20
    assert m["roe"] == 25.0 and m["gross_margin"] == 60.0     # decimals → percent
    assert m["ev_ebitda"] == 12.0                              # 1.2e9 / 1e8


def test_rank_pctile():
    rows = [{"pe": 10}, {"pe": 20}, {"pe": 30}, {"pe": 40}]
    assert md._rank_pctile(rows, "pe", 10) == 25
    assert md._rank_pctile(rows, "pe", 40) == 100
    assert md._rank_pctile(rows, "pe", None) is None
    assert md._rank_pctile([{"pe": 1}, {"pe": 2}], "pe", 1) is None   # <3 → not meaningful


def test_peer_verdict_cheap_high_quality_is_mispricing():
    rows = [{"is_self": True, "roe": 30}, {"roe": 10}, {"roe": 15}, {"roe": 12}]
    pct = {"ev_ebitda": 20, "pe": 25, "roe": 80, "gross_margin": 70, "net_margin": 65}
    verdict, flag = md.peer_verdict_and_flag(rows, pct)
    assert verdict.startswith("便宜")          # cheapest 30% + ROE above peer median
    assert flag and "错杀" in flag


def test_peer_verdict_expensive_low_quality():
    rows = [{"is_self": True, "roe": 5}, {"roe": 20}, {"roe": 25}, {"roe": 22}]
    pct = {"ev_ebitda": 85, "pe": 80, "roe": 10, "gross_margin": 20, "net_margin": 15}
    verdict, flag = md.peer_verdict_and_flag(rows, pct)
    assert verdict.startswith("偏贵") and flag and "高估" in flag


def test_peer_comparison_non_us_graceful():
    p = md.peer_comparison("600519", "A股")
    assert p["rows"] == [] and p["warnings"] and "A股" in p["warnings"][0]


def test_snapshot_unsupported_market_is_graceful_stub():
    s = md.snapshot("00700", "港股")
    assert s["ticker"] == "00700"
    assert s["warnings"] and "港股" in s["warnings"][0]
    assert s["metrics"] == {} and s["financials"] == {}
