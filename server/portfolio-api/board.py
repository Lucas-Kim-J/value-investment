"""Market board — pure scoring for the 自上而下「市场」看板 (体温计 + 板块热力图).

Same split as cycle.py/market_cycle.py: this file is pure + unit-tested; market_board.py
does the I/O (SSGA holdings, multpl P/E, yfinance sector ETFs + breadth) and feeds these
scorers. Numbers in → labels/levels out; the AI only interprets, never sources.

Three top-of-page 体温计 (valuation / concentration / breadth) + a per-sector 热力 score
(RRG-style relative strength). "Crowding" here is an explicit PROXY (valuation × momentum
× concentration), not measured positioning — the data layer/UI must say so.
"""
from __future__ import annotations


def valuation_gauge(pe_percentile: float | None, cape_percentile: float | None) -> dict:
    """市场是否高位：blend of available whole-market valuation percentiles (S&P P/E, CAPE).
    High percentile = expensive = caps forward returns."""
    pcts = [p for p in (pe_percentile, cape_percentile) if p is not None]
    if not pcts:
        return {"percentile": None, "level": None, "label": "数据缺失", "note": ""}
    pct = round(sum(pcts) / len(pcts), 1)
    if pct >= 90:
        level, label, note = 4, "极贵", "估值天花板——远期回报受限，提高安全边际、偏价值"
    elif pct >= 70:
        level, label, note = 3, "偏贵", "估值偏高，安全边际收窄"
    elif pct >= 30:
        level, label, note = 2, "中性", ""
    else:
        level, label, note = 1, "便宜", "估值在历史便宜区"
    return {"percentile": pct, "level": level, "label": label, "note": note}


def breadth_gauge(pct_above_200: float | None, pct_above_50: float | None) -> dict:
    """市场广度：% of index constituents above their 200/50-day MA. High = broad/healthy;
    low = a few names carrying the index (fragile)."""
    if pct_above_200 is None:
        return {"pct_above_200": None, "pct_above_50": pct_above_50, "level": None,
                "label": "数据缺失", "healthy": None}
    p = pct_above_200
    if p >= 70:
        level, label, healthy = 4, "广度强健", True
    elif p >= 50:
        level, label, healthy = 3, "广度中性", True
    elif p >= 30:
        level, label, healthy = 2, "广度偏弱", False
    else:
        level, label, healthy = 1, "广度极弱（超卖/少数股撑盘）", False
    return {"pct_above_200": round(p, 1), "pct_above_50": (round(pct_above_50, 1) if pct_above_50 is not None else None),
            "level": level, "label": label, "healthy": healthy}


def concentration_gauge(top_n_weight: float | None, herfindahl: float | None,
                        rsp_spy_percentile: float | None, top_n: int = 7) -> dict:
    """集中度：how much a few mega-caps dominate. top_n_weight = combined % of the N largest;
    Herfindahl = Σwᵢ² (×10000); rsp_spy_percentile = equal-weight÷cap-weight ratio's percentile
    (low = cap-weight winning = narrow leadership)."""
    bits, flags = [], 0
    if top_n_weight is not None:
        bits.append(f"前{top_n}大权重 {top_n_weight:.0f}%")
        if top_n_weight >= 30:
            flags += 1
    if herfindahl is not None:
        bits.append(f"HHI {herfindahl:.0f}")
    if rsp_spy_percentile is not None:
        bits.append(f"等权/市值比处 {rsp_spy_percentile:.0f}% 分位")
        if rsp_spy_percentile <= 25:
            flags += 1
    if top_n_weight is None and rsp_spy_percentile is None:
        return {"top_n_weight": None, "herfindahl": herfindahl, "rsp_spy_percentile": rsp_spy_percentile,
                "top_n": top_n, "concentrated": None, "label": "数据缺失", "detail": "；".join(bits)}
    concentrated = flags >= 1
    label = "高度集中（少数大票主导）" if concentrated else "集中度温和"
    return {"top_n_weight": (round(top_n_weight, 1) if top_n_weight is not None else None),
            "herfindahl": (round(herfindahl, 0) if herfindahl is not None else None),
            "rsp_spy_percentile": rsp_spy_percentile, "top_n": top_n,
            "concentrated": concentrated, "label": label, "detail": "；".join(bits)}


def herfindahl(weights_pct) -> float | None:
    """HHI = Σ(weight%)². Input weights in percent (e.g. 7.2 for 7.2%)."""
    ws = [w for w in (weights_pct or []) if w is not None]
    if not ws:
        return None
    return round(sum(w * w for w in ws), 1)


# RRG-style quadrant from relative strength: 6m = relative-strength level, 3m = momentum.
_QUADRANTS = {(True, True): "领先", (True, False): "转弱", (False, False): "落后", (False, True): "改善"}


def sector_heat(rs_6m: float | None, rs_3m: float | None) -> dict:
    """One sector's heat vs the market. rs_6m / rs_3m = excess return vs SPY over 6m / 3m
    (decimals, e.g. 0.21 = +21%). Quadrant = RRG-style; heat = blended excess %."""
    if rs_6m is None or rs_3m is None:
        return {"quadrant": "数据缺失", "heat": None, "rs_6m": None, "rs_3m": None}
    quadrant = _QUADRANTS[(rs_6m >= 0, rs_3m >= 0)]
    heat = round((rs_6m + rs_3m) / 2 * 100, 1)
    return {"quadrant": quadrant, "heat": heat,
            "rs_6m": round(rs_6m * 100, 1), "rs_3m": round(rs_3m * 100, 1)}


def market_temperature(valuation: dict, breadth: dict, concentration: dict) -> dict:
    """One-line 市场体温 summary tying the three gauges together (for the page header)."""
    v = (valuation or {}).get("label", "—")
    b = (breadth or {}).get("label", "—")
    hot = (valuation or {}).get("level") == 4 and not (breadth or {}).get("healthy", True)
    note = ("估值极贵 + 广度走弱 = 典型晚周期/少数股撑盘，风险偏高" if hot
            else "综合估值与广度看市场温度")
    return {"valuation": v, "breadth": b,
            "concentrated": (concentration or {}).get("concentrated"), "hot": hot, "note": note}
