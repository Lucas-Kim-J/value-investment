"""市场情绪 — pure scoring (CNN 恐惧贪婪 + VIX 期限结构).

Read CONTRARIAN: extreme fear = often a bottom (lean bullish), extreme greed = froth
(lean cautious). Numbers fetched in market_sentiment.py; this file only labels.
"""
from __future__ import annotations


def fg_gauge(score: float | None) -> dict:
    """CNN Fear & Greed 0–100 → 5-level label + contrarian read."""
    if score is None:
        return {"score": None, "level": None, "label": "数据缺失", "contrarian": ""}
    s = round(score, 1)
    if s < 25:
        lvl, lab, c = 1, "极度恐惧", "逆向偏多（历史底部区常在此）"
    elif s < 45:
        lvl, lab, c = 2, "恐惧", "偏谨慎乐观"
    elif s < 55:
        lvl, lab, c = 3, "中性", ""
    elif s < 75:
        lvl, lab, c = 4, "贪婪", "保持纪律、别追高"
    else:
        lvl, lab, c = 5, "极度贪婪", "逆向偏空（过热，提防回撤）"
    return {"score": s, "level": lvl, "label": lab, "contrarian": c}


def composite(fg: dict | None, vix_lens) -> dict:
    """One-line 情绪 summary tying F&G + VIX term structure together."""
    parts = []
    if fg and fg.get("label") and fg["label"] != "数据缺失":
        parts.append(f"恐惧贪婪 {fg['label']}({fg.get('score')})")
    if vix_lens:
        parts.append(f"波动率 {vix_lens[1]}")
    if not parts:
        return {"label": "数据缺失", "note": ""}
    return {"label": " · ".join(parts), "note": (fg or {}).get("contrarian") or ""}
