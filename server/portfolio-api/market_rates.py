"""Fetch FRED (+ akshare LPR) → assemble the 利率与央行 snapshot via rates.py.

I/O here; rates.py only scores. All "future path" numbers come straight from FRED
(2Y curve for the market-implied leg, FEDTARMD for the Fed dot-plot leg) — we never
model/predict a path. Needs VI_FRED_API_KEY (configured in prod). Best-effort.
"""
from __future__ import annotations

import market_cycle as _mc   # reuse _fred + _FRED_KEY
import rates

RATES_SCHEMA = 1


def _latest(sid: str):
    o = _mc._fred(sid, limit=1, sort="desc")
    return o[0] if o else None        # (date, value)


def _series(sid: str, n: int):
    return _mc._fred(sid, limit=n, sort="desc") or []


def _china_lpr() -> dict:
    try:
        import akshare as ak
        df = ak.macro_china_lpr()
        out = {}
        for col, key in (("LPR1Y", "1Y"), ("LPR5Y", "5Y")):
            if col in df.columns:
                s = df[col].dropna()
                if len(s):
                    out[key] = round(float(s.iloc[-1]), 2)
        return out
    except Exception:  # noqa: BLE001
        return {}


def policy_rates() -> tuple:
    """(display rows, target_upper, target_lower)."""
    rows = []
    up = lo = None
    u, l, eff = _latest("DFEDTARU"), _latest("DFEDTARL"), _latest("DFF")
    if u and l:
        up, lo = u[1], l[1]
        rows.append({"name": "🇺🇸 美联储 联邦基金", "value": f"{lo:.2f}–{up:.2f}%",
                     "detail": (f"有效利率 {eff[1]:.2f}%" if eff else ""), "asof": u[0]})
    lpr = _china_lpr()
    if lpr.get("1Y") is not None:
        five = f" · 5Y {lpr['5Y']:.2f}%" if lpr.get("5Y") is not None else ""
        rows.append({"name": "🇨🇳 中国 LPR", "value": f"1Y {lpr['1Y']:.2f}%{five}", "detail": "", "asof": None})
    return rows, up, lo


def future_path(up: float | None, lo: float | None) -> dict:
    """Two legs: 腿A market-implied (2Y vs policy) + 腿B Fed dot plot (FEDTARMD)."""
    mid = (up + lo) / 2 if (up is not None and lo is not None) else None
    dgs2 = _latest("DGS2")
    leg_a = rates.implied_path(dgs2[1] if dgs2 else None, up, lo)
    byyear = {}
    for d, v in _series("FEDTARMD", 12):     # desc; one obs per future year
        byyear.setdefault(d[:4], v)
    pts = sorted(((int(y), v) for y, v in byyear.items()), key=lambda x: x[0])
    leg_b = rates.dot_plot(pts, current_mid=mid)
    t10yff = _latest("T10YFF")
    return {
        "market_implied": leg_a,
        "dot_plot": leg_b,
        "comparison": rates.path_comparison(leg_a["direction"] if leg_a else None,
                                            leg_b["direction"] if leg_b else None),
        "t10yff": (t10yff[1] if t10yff else None),
    }


def _yoy_indicator(sid: str, name: str) -> dict | None:
    s = _series(sid, 16)
    if len(s) < 13:
        return None
    now = rates.yoy(s[0][1], s[12][1])
    ago = rates.yoy(s[3][1], s[15][1]) if len(s) >= 16 else None
    return {"name": name, "value": (f"{now:.1f}%" if now is not None else "—"),
            "trend": rates.trend(now, ago, rising="升温", falling="降温"), "asof": s[0][0]}


def macro() -> list:
    out = []
    for sid, name in (("CPIAUCSL", "CPI 同比"), ("PCEPILFE", "核心 PCE 同比")):
        ind = _yoy_indicator(sid, name)
        if ind:
            out.append(ind)
    un = _series("UNRATE", 7)
    if un:
        out.append({"name": "失业率", "value": f"{un[0][1]:.1f}%",
                    "trend": rates.trend(un[0][1], (un[6][1] if len(un) >= 7 else None),
                                         rising="上升(走弱)", falling="下降(走强)"), "asof": un[0][0]})
    pay = _series("PAYEMS", 2)
    if len(pay) >= 2:
        out.append({"name": "非农(月增)", "value": f"{round(pay[0][1] - pay[1][1]):+d}k",
                    "trend": None, "asof": pay[0][0]})
    return out


def us_rates() -> dict:
    warnings: list[str] = []
    if not _mc._FRED_KEY:
        warnings.append("未配置 VI_FRED_API_KEY，利率数据缺失")
    pr, up, lo = policy_rates()
    if up is None:
        warnings.append("美联储政策利率缺失")
    fp = future_path(up, lo)
    mac = macro()
    if not mac:
        warnings.append("关键宏观数据缺失")
    return {"_schema": RATES_SCHEMA, "market": "美股", "policy_rates": pr,
            "future_path": fp, "macro": mac, "fred_enabled": bool(_mc._FRED_KEY), "warnings": warnings}
