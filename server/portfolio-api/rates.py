"""利率与央行 — pure scoring for the 市场 page's rates module.

The honest "未来怎么样" has two legs, neither of which we model:
  · 腿A 市场隐含: the 2Y Treasury vs the current policy rate (2Y ≈ avg expected policy
    over 2y + term premium). Below policy = market pricing cuts; above = pricing
    hikes / reflation.
  · 腿B 官方点阵图: the FOMC SEP median path (FRED FEDTARMD), straight from the Fed.
The GAP between them is itself the signal (market more dovish/hawkish than the Fed).
All numbers are fetched (market_rates.py); this file only labels. Pure + unit-tested.
"""
from __future__ import annotations


def implied_path(dgs2: float | None, target_upper: float | None,
                 target_lower: float | None = None) -> dict | None:
    """腿A: market-implied direction from the 2Y vs the policy rate."""
    if dgs2 is None or target_upper is None:
        return None
    lower = target_lower if target_lower is not None else target_upper
    mid = (target_upper + lower) / 2
    gap_mid = round((dgs2 - mid) * 100)        # bps vs policy midpoint
    if dgs2 < target_upper - 0.12:
        n = (target_upper - dgs2) / 0.25
        direction = "降息"
        note = f"2Y 国债 {dgs2:.2f}% 低于政策上限 {target_upper:.2f}% → 市场隐含降息（约 {n:.0f} 次·25bp 计）"
    elif dgs2 > target_upper + 0.12:
        direction = "偏紧 / 不降息"
        note = f"2Y 国债 {dgs2:.2f}% 高于政策利率 → 市场未 price in 降息（含通胀/期限溢价）"
    else:
        direction = "持平"
        note = f"2Y 国债 {dgs2:.2f}% 与政策利率接近 → 市场隐含基本持平"
    return {"dgs2": dgs2, "gap_bps": gap_mid, "direction": direction, "note": note}


def dot_plot(points, current_mid: float | None = None) -> dict | None:
    """腿B: FOMC dot-plot median path. points = [(year:int, median:float), …] ascending."""
    pts = [(y, v) for y, v in (points or []) if v is not None]
    if not pts:
        return None
    ref = current_mid if current_mid is not None else pts[0][1]
    last = pts[-1][1]
    direction = "降息" if last < ref - 0.05 else "加息" if last > ref + 0.05 else "持平"
    head = f"自当前 {current_mid:.2f}% " if current_mid is not None else ""
    note = "FOMC 点阵图中位数：" + " → ".join(f"{y} {v:.2f}%" for y, v in pts) + f"（{head}看{direction}）"
    return {"points": pts, "direction": direction, "note": note}


def path_comparison(market_dir: str | None, fed_dir: str | None) -> str:
    """The high-signal part: market vs Fed. Both are real, neither is our prediction."""
    if not market_dir or not fed_dir:
        return ""
    dovish_mkt = market_dir == "降息"
    hawk_mkt = market_dir.startswith("偏紧")
    if dovish_mkt and fed_dir == "降息":
        return "市场与 Fed 方向一致（都偏降息）。"
    if hawk_mkt and fed_dir == "降息":
        return "★市场比 Fed 点阵图更鹰——不太相信会按点阵图降息（可能在 price in 通胀粘性/再通胀）。"
    if dovish_mkt and fed_dir in ("持平", "加息"):
        return "★市场比 Fed 更鸽——抢跑降息（常见于市场担心增长/衰退）。"
    return f"市场隐含{market_dir}，Fed 指引{fed_dir}。"


def yoy(now: float | None, year_ago: float | None) -> float | None:
    """Year-over-year % change (for CPI/PCE levels)."""
    if now is None or year_ago in (None, 0):
        return None
    return round((now / year_ago - 1) * 100, 1)


def trend(now: float | None, ref: float | None, *, rising: str, falling: str,
          flat: str = "持平", eps: float = 0.1) -> str | None:
    """Direction label of `now` vs an earlier `ref` (eps = 持平 band, same units)."""
    if now is None or ref is None:
        return None
    d = now - ref
    return rising if d > eps else falling if d < -eps else flat
