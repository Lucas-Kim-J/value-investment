"""宏观资金传导 (macro capital transmission) — the 2nd layer of the 资金传导 pillar.

Two halves, both data-grounded:
  1. macro ENVIRONMENT (market-level): rates level + trend + yield-curve state
     (US via ^TNX/^IRX; A股 via 10Y + LPR + M2) — fetched in market_data, passed here.
  2. company SENSITIVITY (firm-level): how this company transmits from rates —
     leverage (D/E), interest coverage (EBIT/利息), and duration proxy (high P/E /
     high growth = long-duration cash flows = more rate-sensitive).
Then a transmission note tying environment → company.

Pure functions over already-fetched numbers → unit-testable, no fabrication.
"""
from __future__ import annotations


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return None if (x != x or x in (float("inf"), float("-inf"))) else x


def rate_trend(now, year_ago, band=0.3):
    """利率趋势 over ~1y, in percentage points (band = 持平 threshold)."""
    n, a = _f(now), _f(year_ago)
    if n is None or a is None:
        return None
    d = n - a
    return "上行" if d > band else "下行" if d < -band else "持平"


def curve_state(slope):
    """收益率曲线 (10Y − short), in pp: <0 倒挂 (recession/紧缩信号), 0–0.5 平坦, else 正常."""
    s = _f(slope)
    if s is None:
        return None
    return "倒挂" if s < 0 else "平坦" if s < 0.5 else "正常"


def sensitivity(*, d2e=None, interest_coverage=None, pe=None, growth=None):
    """Firm rate-sensitivity: leverage + interest coverage + cash-flow duration."""
    pts, drivers = 0, []
    de = _f(d2e)
    if de is not None:
        if de > 150:
            pts += 2; drivers.append(f"高杠杆 D/E {de:.0f}%")
        elif de > 80:
            pts += 1; drivers.append(f"中等杠杆 D/E {de:.0f}%")
        else:
            drivers.append(f"低杠杆 D/E {de:.0f}%")
    cov = _f(interest_coverage)
    if cov is not None:
        if cov < 4:
            pts += 2; drivers.append(f"利息覆盖偏弱 {cov:.1f}×")
        elif cov < 8:
            pts += 1; drivers.append(f"利息覆盖一般 {cov:.1f}×")
        else:
            drivers.append(f"利息覆盖充足 {cov:.1f}×")
    p = _f(pe)
    if p is not None:
        if p > 35:
            pts += 2; drivers.append(f"高P/E {p:.0f}（长久期，对利率更敏感）")
        elif p > 20:
            pts += 1; drivers.append(f"P/E {p:.0f}（中等久期）")
        else:
            drivers.append(f"低P/E {p:.0f}（短久期）")
    g = _f(growth)
    if g is not None and g > 25:
        pts += 1; drivers.append(f"高增长 {g:.0f}%（远期现金流占比高）")
    if not drivers:
        return {"score": "数据不足", "drivers": []}
    score = "高" if pts >= 4 else "中" if pts >= 2 else "低"
    return {"score": score, "drivers": drivers}


def transmission_note(env, sens, market):
    """One-line macro→company transmission, tying environment to firm sensitivity."""
    if not env:
        return "宏观环境数据缺失，无法评估传导。"
    parts = []
    ty = env.get("ten_year")
    if ty is not None:
        seg = f"当前 10Y 利率 {ty:.2f}%"
        if env.get("rate_trend"):
            seg += f"（近一年{env['rate_trend']}）"
        if env.get("curve_state"):
            seg += f"，收益率曲线{env['curve_state']}"
        parts.append(seg)
    if market == "A股":
        if env.get("lpr_1y") is not None:
            parts.append(f"1年期 LPR {env['lpr_1y']:.2f}%")
        if env.get("m2_growth") is not None:
            parts.append(f"M2 同比 {env['m2_growth']:.1f}%")
    sc = sens.get("score")
    if sc and sc != "数据不足":
        tail = "；".join(sens.get("drivers", [])[:3])
        impact = {"高": "对利率高度敏感——加息/高利率是明显逆风（偿债+估值双压）",
                  "中": "中等利率敏感——高利率主要压估值",
                  "低": "对利率不敏感——宏观逆风传导有限"}.get(sc, "")
        parts.append(f"该公司{tail} → {impact}")
    return "；".join(parts) + "。"


def assemble(env, *, d2e=None, interest_coverage=None, pe=None, growth=None, market="美股"):
    sens = sensitivity(d2e=d2e, interest_coverage=interest_coverage, pe=pe, growth=growth)
    e = dict(env or {})
    return {"env": e, "sensitivity": sens, "note": transmission_note(e, sens, market)}
