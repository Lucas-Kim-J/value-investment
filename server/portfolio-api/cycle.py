"""Market-level CYCLE compass (周期罗盘) — pure scoring, no I/O.

Self-bottom-up value analysis tells you *what to buy and what it's worth*; this
module adds the top-down layer: *where are we in the cycle, and what does that
mean for position size / style / expected return*. It scores several independent
"cycle lenses" from real numbers the data layer fetches (the AI never sources
these), blends them into a 5-level cycle position, derives an asset tilt, and —
the part that answers "right value call but a bad up-cycle still underperforms" —
overlays the per-stock VALUE verdict with the market CYCLE into concrete guidance.

Every function here is pure + unit-tested. Convention: a lens sub-score is an int
in [-2, +2] where **positive = supportive of risk assets / earlier in the cycle**,
negative = late-cycle / risk-off. Valuation is deliberately *inverse* (expensive =
negative) because rich valuations cap forward returns.

Lens inputs are plain numbers already reduced by the data layer; pass None for any
lens whose data we couldn't fetch (e.g. FRED without an API key) and it's simply
dropped from the blend (with a note), never fabricated.
"""
from __future__ import annotations

import math

# Lens weights in the REGIME blend. Credit + liquidity move first and deepest
# (Marks), so they carry more; volatility/sentiment is a lighter confirmer.
# Valuation is deliberately NOT here: rich valuations don't *time* the cycle (an
# expensive market can still be early/mid-cycle) — they cap forward returns. So
# valuation is surfaced only as the return-cap flag + inside the value×cycle
# overlay, never as a regime driver.
_WEIGHTS = {
    "yield_curve": 1.0,
    "credit": 1.5,
    "liquidity": 1.5,
    "volatility": 0.5,
}

# 5 cycle positions (level 1 = deep risk-off … 5 = risk-on).
POSITIONS = {
    1: "衰退 / risk-off",
    2: "放缓 / 偏防御",
    3: "晚周期 / 中性",
    4: "复苏 / 偏多",
    5: "扩张 / risk-on",
}


# --------------------------------------------------------------------------- #
# Per-lens scorers — each returns (score:int in -2..2, label:str, detail:str)
# --------------------------------------------------------------------------- #

def recession_prob_from_curve(t10y3m: float | None) -> float | None:
    """Estrella–Trubin probit: P(recession in ~12m) = Φ(-0.6045 - 0.7374·spread),
    spread = 10Y minus 3M in percentage points. Heuristic, but a well-known one."""
    if t10y3m is None:
        return None
    return _norm_cdf(-0.6045 - 0.7374 * t10y3m)


def yield_curve_lens(t10y3m: float | None, recession_prob: float | None = None):
    """Yield-curve / recession lens from the 10Y–3M spread (+ optional probit)."""
    if t10y3m is None:
        return None
    if recession_prob is None:
        recession_prob = recession_prob_from_curve(t10y3m)
    if recession_prob is not None and recession_prob >= 0.35:
        return (-2, "曲线倒挂·衰退概率高", f"10Y-3M={t10y3m:+.2f}pp，衰退概率≈{recession_prob*100:.0f}%")
    if t10y3m < 0:
        return (-1, "曲线倒挂", f"10Y-3M={t10y3m:+.2f}pp（倒挂，晚周期预警）")
    if t10y3m < 0.5:
        return (0, "曲线偏平", f"10Y-3M={t10y3m:+.2f}pp")
    if t10y3m < 1.5:
        return (1, "曲线正常陡峭", f"10Y-3M={t10y3m:+.2f}pp")
    return (2, "曲线陡峭·早周期", f"10Y-3M={t10y3m:+.2f}pp（陡峭，常见于复苏早段）")


def valuation_lens(cape_percentile: float | None, cape: float | None = None):
    """Valuation lens (INVERSE): high CAPE percentile = expensive = caps returns."""
    if cape_percentile is None:
        return None
    v = f"CAPE={cape:.1f}，" if cape is not None else ""
    if cape_percentile < 30:
        return (2, "估值便宜", f"{v}处历史 {cape_percentile:.0f}% 分位（便宜区）")
    if cape_percentile < 70:
        return (0, "估值中性", f"{v}处历史 {cape_percentile:.0f}% 分位")
    if cape_percentile < 85:
        return (-1, "估值偏贵", f"{v}处历史 {cape_percentile:.0f}% 分位")
    return (-2, "估值极贵", f"{v}处历史 {cape_percentile:.0f}% 分位（天花板，压低远期回报）")


def volatility_lens(ivts: float | None):
    """VIX term-structure lens. IVTS = VIX/VIX3M. Contango (<1) is the calm norm
    (~80% of the time); backwardation (>1) flags near-term fear."""
    if ivts is None:
        return None
    if ivts < 0.85:
        return (1, "波动率 contango（健康）", f"VIX/VIX3M={ivts:.2f}（远端高于近端，市场平静）")
    if ivts < 0.95:
        return (0, "波动率 contango（温和）", f"VIX/VIX3M={ivts:.2f}")
    if ivts < 1.0:
        return (-1, "波动率结构走平（预警）", f"VIX/VIX3M={ivts:.2f}（接近 backwardation）")
    return (-2, "波动率 backwardation（恐慌）", f"VIX/VIX3M={ivts:.2f}（近端高于远端，risk-off）")


def credit_lens(hy_spread_percentile: float | None, hy_spread: float | None = None):
    """Credit lens from high-yield OAS percentile. Low percentile = loose credit /
    risk-on (also complacency); high/blowing-out = credit stress / risk-off."""
    if hy_spread_percentile is None:
        return None
    v = f"HY利差={hy_spread:.2f}%，" if hy_spread is not None else ""
    if hy_spread_percentile < 25:
        return (2, "信用极宽松", f"{v}处历史 {hy_spread_percentile:.0f}% 分位（risk-on，偏自满）")
    if hy_spread_percentile < 50:
        return (1, "信用宽松", f"{v}处历史 {hy_spread_percentile:.0f}% 分位")
    if hy_spread_percentile < 75:
        return (-1, "信用收紧", f"{v}处历史 {hy_spread_percentile:.0f}% 分位")
    return (-2, "信用紧张 / 走阔", f"{v}处历史 {hy_spread_percentile:.0f}% 分位（risk-off）")


def liquidity_lens(net_liq_slope: float | None, m2_yoy: float | None):
    """Liquidity lens from Fed net-liquidity 4-week slope (+/-) and M2 YoY."""
    if net_liq_slope is None and m2_yoy is None:
        return None
    bits, score = [], 0
    if net_liq_slope is not None:
        bits.append(f"净流动性4周斜率={net_liq_slope:+.1f}%")
        score += 1 if net_liq_slope > 0 else -1
    if m2_yoy is not None:
        bits.append(f"M2同比={m2_yoy:+.1f}%")
        score += 1 if m2_yoy > 0 else -1
    score = max(-2, min(2, score))
    label = "流动性扩张" if score > 0 else ("流动性收缩" if score < 0 else "流动性中性")
    return (score, label, "；".join(bits))


def cape_discount_flag(cape_percentile: float | None) -> tuple[bool, str]:
    """The crux: even in an up-cycle, a >90th-pct CAPE caps forward returns →
    raise this flag so the verdict says 'participate but de-risk / margin of safety'."""
    if cape_percentile is not None and cape_percentile >= 90:
        return (True, f"估值处历史 {cape_percentile:.0f}% 分位——即便周期顺风，远期回报受限，降 beta、提高安全边际、偏价值/便宜板块。")
    return (False, "")


# --------------------------------------------------------------------------- #
# Blend → cycle position + regime
# --------------------------------------------------------------------------- #

def composite_cycle(lenses: dict, sahm: float | None = None) -> dict:
    """Blend available lens scores (weighted mean) → 5-level cycle position.
    `lenses` maps lens-key → (score,label,detail) or None. Sahm ≥0.5 is a hard
    circuit-breaker that forces level 1 regardless of the blend."""
    used, num, den = {}, 0.0, 0.0
    for key, w in _WEIGHTS.items():
        lens = lenses.get(key)
        if not lens:
            continue
        score = lens[0]
        used[key] = lens
        num += score * w
        den += w
    avg = (num / den) if den else None
    breaker = sahm is not None and sahm >= 0.5

    if breaker:
        level = 1
    elif avg is None:
        level = 3
    elif avg <= -1.0:
        level = 1
    elif avg <= -0.3:
        level = 2
    elif avg < 0.3:
        level = 3
    elif avg < 1.0:
        level = 4
    else:
        level = 5

    missing = [k for k in _WEIGHTS if not lenses.get(k)]
    return {
        "score": round(avg, 2) if avg is not None else None,
        "level": level,
        "position": POSITIONS[level],
        "tailwind": _tailwind(level),
        "sahm_breaker": breaker,
        "lenses_used": list(used.keys()),
        "lenses_missing": missing,
    }


def _tailwind(level: int) -> str:
    """Collapse the 5-level position to the 3-state used by the value×cycle overlay."""
    return "顺风" if level >= 4 else ("逆风" if level <= 2 else "中性")


# --------------------------------------------------------------------------- #
# Regime → asset tilt
# --------------------------------------------------------------------------- #
# 占优 ✓ / 中性 ○ / 回避 ✕  per asset class, by cycle level. Probabilistic priors,
# not switches (e.g. 2023 broke "rates up → value beats growth"). Source: Merrill
# investment clock + Marks/Dalio cycle playbook (see research notes).
_TILT = {
    5: {"价值股": "○", "成长股": "✓", "防御股": "✕", "长债": "○", "现金": "✕", "黄金": "○", "商品": "✓", "加密": "✓"},
    4: {"价值股": "✓", "成长股": "✓", "防御股": "✕", "长债": "○", "现金": "✕", "黄金": "○", "商品": "○", "加密": "✓"},
    3: {"价值股": "✓", "成长股": "○", "防御股": "✓", "长债": "○", "现金": "○", "黄金": "✓", "商品": "○", "加密": "✕"},
    2: {"价值股": "○", "成长股": "✕", "防御股": "✓", "长债": "✓", "现金": "✓", "黄金": "✓", "商品": "○", "加密": "✕"},
    1: {"价值股": "○", "成长股": "✕", "防御股": "✓", "长债": "✓", "现金": "✓", "黄金": "○", "商品": "✕", "加密": "✕"},
}


def asset_tilt(level: int) -> dict:
    return dict(_TILT.get(level, _TILT[3]))


# --------------------------------------------------------------------------- #
# Value × Cycle overlay — the answer to "right call, wrong cycle"
# --------------------------------------------------------------------------- #
# rows = value verdict {便宜/合理/贵}, cols = cycle tailwind {顺风/中性/逆风}.
_OVERLAY = {
    ("便宜", "顺风"): ("重仓·最高确信", "价值与周期共振：可标准/重仓建仓。"),
    ("便宜", "中性"): ("标准建仓", "价值占优、周期中性：正常建仓，留余地。"),
    ("便宜", "逆风"): ("小仓分批·潜伏", "便宜但周期逆风：小仓分批、等周期确认，别一次满仓——这正是'判断对但回报有限'的解法。"),
    ("合理", "顺风"): ("顺势参与", "估值合理、周期顺风：可顺势参与，控好仓位。"),
    ("合理", "中性"): ("观望 / 择时", "估值与周期都不极端：观望或小仓择时。"),
    ("合理", "逆风"): ("回避", "合理估值 + 逆风周期：性价比低，回避。"),
    ("贵", "顺风"): ("减仓·只做趋势尾段", "贵但周期顺风：只做趋势尾段，严设退出，警惕反身性。"),
    ("贵", "中性"): ("减仓", "贵 + 周期中性：降低敞口。"),
    ("贵", "逆风"): ("清仓 / 对冲", "贵 + 逆风：最差象限，清仓或对冲。"),
}


def value_cycle_overlay(value_verdict: str | None, tailwind: str | None) -> dict | None:
    """Combine the per-stock value verdict (便宜/合理/贵) with the market cycle
    tailwind (顺风/中性/逆风) into position-sizing + style guidance."""
    if value_verdict not in ("便宜", "合理", "贵") or tailwind not in ("顺风", "中性", "逆风"):
        return None
    stance, note = _OVERLAY[(value_verdict, tailwind)]
    return {"value": value_verdict, "tailwind": tailwind, "stance": stance, "note": note}


def _norm_cdf(x: float) -> float:
    """Standard-normal CDF via erf (stdlib only)."""
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))
