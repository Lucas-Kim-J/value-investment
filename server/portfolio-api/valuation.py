"""Valuation-consensus signal engine for 公司分析.

Turns real fetched data into the methodology's quantified valuation signals — so we
measure what the market is PRICING IN (the consensus), against which the AI can later
look for a *non-consensus* (variant) view. Pure computation, no fabrication; every
output carries the numbers + assumptions it was derived from.

Tools (the methodology's 四工具三角验证):
  ① 反向DCF  — solve for the annual owner-earnings growth the current price implies,
               then judge it against the company's own historical CAGR.
  ② 历史P/E分位 — current P/E vs its own history (0-25% = historically cheap).
  ③ EV/EBIT    — computed; the peer-relative verdict comes from the peer engine (pending).
  ④ Owner-Earnings Yield vs 10Y — OE/MV minus the risk-free rate (>+4% = a real hurdle clear).

"≥2 independent tools say cheap" → worth deep research.
"""
from __future__ import annotations


def _num(v):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if (f != f or f in (float("inf"), float("-inf"))) else f


def _cagr(series):
    """Compound annual growth between first and last positive points of a series."""
    xs = [x for x in (series or []) if x is not None and x > 0]
    if len(xs) < 2:
        return None
    n = len(xs) - 1
    return round((xs[-1] / xs[0]) ** (1 / n) - 1, 4)


def reverse_dcf_growth(owner_earnings, market_value, discount=0.09, terminal=0.025, years=10):
    """Solve (bisection) for the explicit-stage growth g that makes a 10y-DCF of
    owner earnings equal today's market value. = "what the price is pricing in"."""
    oe, mv = _num(owner_earnings), _num(market_value)
    if not oe or oe <= 0 or not mv or mv <= 0 or discount <= terminal:
        return None

    def pv(g):
        total = 0.0
        for t in range(1, years + 1):
            total += oe * (1 + g) ** t / (1 + discount) ** t
        e_n = oe * (1 + g) ** years
        tv = e_n * (1 + terminal) / (discount - terminal)
        return total + tv / (1 + discount) ** years

    lo, hi = -0.5, 1.0
    if pv(lo) >= mv:      # cheap even assuming -50% growth
        return lo
    if pv(hi) <= mv:      # expensive even assuming +100% growth
        return hi
    for _ in range(64):   # pv() is monotincreasing in g
        mid = (lo + hi) / 2
        if pv(mid) < mv:
            lo = mid
        else:
            hi = mid
    return round((lo + hi) / 2, 4)


def signals(*, market_cap, owner_earnings, net_debt, ebit, pe_percentile,
            ten_year_yield, hist_rev_cagr=None, hist_eps_cagr=None,
            discount=0.09, terminal=0.025, years=10):
    """Assemble the four-tools scoreboard from real numbers. Each tool returns a
    verdict in {便宜, 合理, 偏贵, 待同行, 数据缺失} + the figure it rests on."""
    mv = _num(market_cap)
    oe = _num(owner_earnings)
    ebit = _num(ebit)
    nd = _num(net_debt) or 0.0
    rf = _num(ten_year_yield)

    tools = []

    # ① 反向DCF
    implied = reverse_dcf_growth(oe, mv, discount, terminal, years)
    ref_cagr = hist_eps_cagr if hist_eps_cagr is not None else hist_rev_cagr
    if implied is None:
        tools.append({"key": "reverse_dcf", "name": "反向DCF", "verdict": "数据缺失",
                      "detail": "需要正的自由现金流与市值"})
    else:
        if ref_cagr is None:
            verdict = "合理" if implied <= 0.10 else "偏贵"
            detail = f"隐含增长 {implied*100:.1f}%/年（缺历史增速对照）"
        elif implied <= ref_cagr:
            verdict, detail = "便宜", f"隐含增长 {implied*100:.1f}% ≤ 历史 {ref_cagr*100:.1f}%（市场预期偏保守）"
        elif implied <= ref_cagr * 1.3 + 0.02:
            verdict, detail = "合理", f"隐含增长 {implied*100:.1f}% ≈ 历史 {ref_cagr*100:.1f}%"
        else:
            verdict, detail = "偏贵", f"隐含增长 {implied*100:.1f}% ≫ 历史 {ref_cagr*100:.1f}%（市场预期乐观）"
        tools.append({"key": "reverse_dcf", "name": "反向DCF", "verdict": verdict, "detail": detail})

    # ② 历史P/E分位
    pep = _num(pe_percentile)
    if pep is None:
        tools.append({"key": "hist_pe", "name": "历史P/E分位", "verdict": "数据缺失", "detail": ""})
    else:
        verdict = "便宜" if pep <= 25 else "偏贵" if pep >= 75 else "合理"
        tools.append({"key": "hist_pe", "name": "历史P/E分位", "verdict": verdict,
                      "detail": f"当前处于历史 {pep:.0f}% 分位（0%=史上最便宜）"})

    # ③ EV/EBIT (absolute now; peer-relative verdict pending the peer engine)
    ev_ebit = None
    if mv and ebit and ebit > 0:
        ev_ebit = round((mv + nd) / ebit, 1)
        tools.append({"key": "ev_ebit", "name": "EV/EBIT", "verdict": "待同行",
                      "detail": f"{ev_ebit}×（需同行对比判贵贱——下个引擎）"})
    else:
        tools.append({"key": "ev_ebit", "name": "EV/EBIT", "verdict": "数据缺失", "detail": ""})

    # ④ Owner-Earnings Yield vs 10Y
    oey = round(oe / mv, 4) if (oe and mv and oe > 0) else None
    if oey is None or rf is None:
        tools.append({"key": "oe_yield", "name": "OE收益率vs10Y", "verdict": "数据缺失",
                      "detail": "需正的自由现金流与无风险利率"})
    else:
        spread = oey - rf
        verdict = "便宜" if spread >= 0.04 else "偏贵" if spread < 0 else "合理"
        tools.append({"key": "oe_yield", "name": "OE收益率vs10Y", "verdict": verdict,
                      "detail": f"OE收益率 {oey*100:.1f}% − 10Y {rf*100:.1f}% = {spread*100:+.1f}%"})

    cheap = sum(1 for t in tools if t["verdict"] == "便宜")
    scored = sum(1 for t in tools if t["verdict"] in ("便宜", "合理", "偏贵"))
    return {
        "tools": tools,
        "cheap_count": cheap,
        "scored_count": scored,
        "deep_research": cheap >= 2,
        "reverse_dcf": {
            "implied_growth": implied,
            "hist_rev_cagr": hist_rev_cagr,
            "hist_eps_cagr": hist_eps_cagr,
            "owner_earnings": oe,
            "assumptions": {"discount_rate": discount, "terminal_growth": terminal, "years": years},
        },
        "ev_ebit": ev_ebit,
        "owner_earnings_yield": oey,
        "ten_year_yield": rf,
        "net_debt": nd,
    }
