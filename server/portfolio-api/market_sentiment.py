"""Fetch CNN 恐惧贪婪 + VIX 期限结构 → 情绪体温计 snapshot via sentiment.py.

CNN's Fear & Greed internal JSON 418s a bare UA — it needs a full browser header set
(Referer + Origin), verified from our host 2026-06. Best-effort + cached; on failure
the gauge degrades to VIX-only (never faked).
"""
from __future__ import annotations

import json
import urllib.request

import cycle as _cyc
import market_cycle as _mc   # reuse vix_term_structure
import sentiment

SENT_SCHEMA = 1
_CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
_CNN_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.cnn.com/markets/fear-and-greed",
    "Origin": "https://www.cnn.com",
}
# CNN subindicator key → 中文名 (each carries its own rating)
_SUBS = {
    "market_momentum_sp500": "市场动量", "stock_price_strength": "价格强度",
    "stock_price_breadth": "涨跌广度", "put_call_options": "期权 Put/Call",
    "market_volatility_vix": "波动率 VIX", "junk_bond_demand": "垃圾债需求",
    "safe_haven_demand": "避险需求",
}
_RATING_CN = {
    "extreme fear": "极度恐惧", "fear": "恐惧", "neutral": "中性",
    "greed": "贪婪", "extreme greed": "极度贪婪",
}


def fear_greed() -> dict | None:
    try:
        req = urllib.request.Request(_CNN_URL, headers=_CNN_HEADERS)
        with urllib.request.urlopen(req, timeout=25) as r:
            d = json.loads(r.read())
        fg = d.get("fear_and_greed") or {}
        subs = []
        for key, name in _SUBS.items():
            v = d.get(key)
            if isinstance(v, dict) and v.get("rating"):
                subs.append({"name": name, "rating": _RATING_CN.get(str(v["rating"]).lower(), v["rating"])})
        return {"score": fg.get("score"), "rating": _RATING_CN.get(str(fg.get("rating")).lower(), fg.get("rating")), "subs": subs}
    except Exception:  # noqa: BLE001
        return None


def us_sentiment() -> dict:
    warnings: list[str] = []
    fg_raw = fear_greed()
    gauge = sentiment.fg_gauge(fg_raw.get("score") if fg_raw else None)
    if fg_raw:
        gauge["rating"] = fg_raw.get("rating")
        gauge["subs"] = fg_raw.get("subs") or []
    else:
        warnings.append("CNN 恐惧贪婪数据缺失（接口偶发改版/限流）")

    vix = _mc.vix_term_structure()
    vlens = _cyc.volatility_lens(vix["ivts"]) if vix else None
    if vix:
        vix_term = {"ivts": vix["ivts"], "vix": vix["vix"], "vix3m": vix["vix3m"],
                    "label": vlens[1] if vlens else "—", "detail": vlens[2] if vlens else ""}
    else:
        vix_term = {"label": "数据缺失"}
        warnings.append("VIX 期限结构缺失")

    return {
        "_schema": SENT_SCHEMA,
        "market": "美股",
        "fear_greed": gauge,
        "vix_term": vix_term,
        "composite": sentiment.composite(gauge, vlens),
        "warnings": warnings,
    }
