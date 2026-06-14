"""Earnings-quality / capital-transmission forensics for 公司分析 (资金传导支柱).

Turns the financial-statement time-series we already fetch into hard, data-backed
red flags — the things that separate "便宜得有理" from a value trap:

  - 利润含金量 (cash conversion): does net income become real cash? (FCF / 净利润)
  - 应计 / 应收存货 (accruals): receivables/inventory growing faster than revenue?
  - 增量 ROIC: is newly-deployed capital earning as much as the existing base, or
    is the company reinvesting at deteriorating returns (which the market often
    extrapolates away)?
  - 资本配置 / 商誉 / 派息: payout vs earnings, goodwill vs equity.

Pure functions over already-extracted series → unit-testable, no network, no
fabrication (missing input → that signal is omitted / 数据不足).
"""
from __future__ import annotations


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if (x != x or x in (float("inf"), float("-inf"))) else x


def _clean(xs):
    return [_f(x) for x in (xs or [])]


def _cagr(series):
    xs = [x for x in _clean(series) if x is not None and x > 0]
    if len(xs) < 2:
        return None
    return round((xs[-1] / xs[0]) ** (1 / (len(xs) - 1)) - 1, 4)


def cash_conversion(net_income, fcf):
    """利润含金量: cumulative FCF / 净利润 over the window (robust to one-off years)."""
    ni, cf = _clean(net_income), _clean(fcf)
    pairs = [(n, c) for n, c in zip(ni, cf) if n is not None and c is not None]
    if not pairs:
        return None
    sni = sum(n for n, _ in pairs)
    scf = sum(c for _, c in pairs)
    latest = pairs[-1]
    cum = round(scf / sni, 2) if sni > 0 else None
    latest_ratio = round(latest[1] / latest[0], 2) if latest[0] and latest[0] > 0 else None
    if cum is None:
        verdict = "数据不足"
    elif cum >= 0.8:
        verdict = "高（利润大多转成了真金白银）"
    elif cum >= 0.5:
        verdict = "一般（部分利润未转成现金）"
    else:
        verdict = "低（纸面利润警示：现金远少于账面利润）"
    return {"cum_fcf_ni": cum, "latest_fcf_ni": latest_ratio, "years": len(pairs), "verdict": verdict}


def accruals(revenue, receivables, inventory):
    """应收/存货 增速 vs 营收增速：长期快于营收 = 盈余质量红旗。"""
    rev_c = _cagr(revenue)
    recv_c = _cagr(receivables)
    inv_c = _cagr(inventory)
    out = {"rev_cagr": rev_c, "recv_cagr": recv_c, "inv_cagr": inv_c,
           "recv_flag": False, "inv_flag": False}
    if rev_c is not None and recv_c is not None:
        out["recv_flag"] = recv_c > rev_c * 1.2 + 0.03 and recv_c > 0
    if rev_c is not None and inv_c is not None:
        out["inv_flag"] = inv_c > rev_c * 1.2 + 0.03 and inv_c > 0
    return out


def incremental_roic(ebit, invested_capital):
    """增量ROIC = ΔEBIT / Δ投入资本，对比期间平均ROIC：衰减=钱越投越不值。"""
    e, ic = _clean(ebit), _clean(invested_capital)
    pairs = [(a, b) for a, b in zip(e, ic) if a is not None and b is not None and b > 0]
    if len(pairs) < 3:
        return None
    avg_roic = round(sum(a / b for a, b in pairs) / len(pairs), 4)
    d_ebit = pairs[-1][0] - pairs[0][0]
    d_ic = pairs[-1][1] - pairs[0][1]
    if d_ic <= 0:
        return {"incremental": None, "avg_roic": avg_roic, "verdict": "期间投入资本未净增加，无法测增量回报"}
    incr = round(d_ebit / d_ic, 4)
    if incr >= avg_roic:
        verdict = "增量回报不输存量（资本配置健康）"
    elif incr >= avg_roic * 0.6:
        verdict = "增量回报略降（留意）"
    else:
        verdict = "增量回报明显衰减（钱越投越不值；市场或仍按旧回报外推）"
    return {"incremental": incr, "avg_roic": avg_roic, "verdict": verdict}


def signals(*, net_income=None, revenue=None, fcf=None, ebit=None,
            receivables=None, inventory=None, goodwill_latest=None, equity_latest=None,
            invested_capital=None, payout_ratio=None):
    """Assemble 盈余质量/资金传导 signals + the methodology's value-trap red flags."""
    out = {"cash_conversion": None, "accruals": None, "incremental_roic": None,
           "goodwill_ratio": None, "payout_ratio": None, "red_flags": [], "flag_count": 0}

    cc = cash_conversion(net_income, fcf)
    out["cash_conversion"] = cc
    acc = accruals(revenue, receivables, inventory)
    if any(v is not None for v in (acc["rev_cagr"], acc["recv_cagr"], acc["inv_cagr"])):
        out["accruals"] = acc
    out["incremental_roic"] = incremental_roic(ebit, invested_capital)

    gw = _f(goodwill_latest)
    eq = _f(equity_latest)
    gw_ratio = round(gw / eq * 100, 1) if (gw is not None and eq and eq > 0) else None
    out["goodwill_ratio"] = gw_ratio
    pr = _f(payout_ratio)
    out["payout_ratio"] = round(pr * 100, 1) if pr is not None else None

    flags = []

    def add(name, hit, detail):
        flags.append({"name": name, "hit": bool(hit), "detail": detail})

    if cc and cc["cum_fcf_ni"] is not None:
        add("经营现金流长期<净利润", cc["cum_fcf_ni"] < 0.8,
            f"累计 FCF/净利润 = {cc['cum_fcf_ni']}（<0.8 视为含金量不足）")
    if out["accruals"]:
        add("应收增速>营收增速", acc["recv_flag"],
            f"应收 CAGR {_pc(acc['recv_cagr'])} vs 营收 CAGR {_pc(acc['rev_cagr'])}")
        add("存货增速>营收增速", acc["inv_flag"],
            f"存货 CAGR {_pc(acc['inv_cagr'])} vs 营收 CAGR {_pc(acc['rev_cagr'])}")
    if gw_ratio is not None:
        add("商誉占净资产>30%", gw_ratio > 30, f"商誉/净资产 = {gw_ratio}%")
    if out["payout_ratio"] is not None:
        add("派息>盈利(>100%)", out["payout_ratio"] > 100,
            f"派息率 = {out['payout_ratio']}%（>100% 即分红超过盈利，可能靠借债）")
    iroic = out["incremental_roic"]
    if iroic and iroic.get("incremental") is not None:
        add("增量ROIC衰减", iroic["incremental"] < (iroic["avg_roic"] or 0) * 0.6,
            f"增量ROIC {_pc(iroic['incremental'])} vs 平均 {_pc(iroic['avg_roic'])}")

    out["red_flags"] = flags
    out["flag_count"] = sum(1 for f in flags if f["hit"])
    return out


def _pc(x):
    return "数据缺失" if x is None else f"{x * 100:.1f}%"


def _range_position(label, values, unit):
    """Current value's position within its own multi-year min–max range (0=trough,
    100=peak). For ~6 annual points a min–max position is meaningful where a
    percentile isn't — it answers 'is this metric at a cyclical peak or trough?'."""
    xs = [_f(x) for x in (values or [])]
    xs = [x for x in xs if x is not None]
    if len(xs) < 3:
        return None
    cur, lo, hi = xs[-1], min(xs), max(xs)
    avg = sum(xs) / len(xs)
    pos = round((cur - lo) / (hi - lo) * 100) if hi > lo else 50
    state = "高位" if pos >= 80 else "低位" if pos <= 20 else "中段"
    return {"name": label, "unit": unit, "current": round(cur, 2), "min": round(lo, 2),
            "max": round(hi, 2), "avg": round(avg, 2), "position": pos, "state": state}


def history_position(financials):
    """历史镜像 (cycle position): where today's profitability/growth sits in the
    company's OWN multi-year range — to catch the market extrapolating a peak (or
    trough) as if it were normal."""
    years = financials.get("years") or []
    rev = [_f(x) for x in (financials.get("revenue") or [])]
    yoy = []
    for i in range(1, len(rev)):
        yoy.append(round((rev[i] / rev[i - 1] - 1) * 100, 2) if (rev[i] is not None and rev[i - 1]) else None)

    metrics = []
    for m in (
        _range_position("净利率", financials.get("net_margin"), "%"),
        _range_position("毛利率", financials.get("gross_margin"), "%"),
        _range_position("营收YoY增速", yoy, "%"),
    ):
        if m:
            metrics.append(m)
    if not metrics:
        return {}

    nm = next((m for m in metrics if m["name"] == "净利率"), None)
    if nm and nm["position"] >= 80:
        note = "盈利能力接近历史高位——若市场按当前高盈利外推，警惕均值回归 / 周期顶（低 P/E 可能是价值陷阱）"
    elif nm and nm["position"] <= 20:
        note = "盈利能力接近历史低位——分清是均值回归机会还是结构性衰退"
    else:
        note = "盈利能力处于历史中段，无明显周期极值"
    return {"span": f"{years[0]}-{years[-1]}" if len(years) >= 2 else "", "metrics": metrics, "note": note}
