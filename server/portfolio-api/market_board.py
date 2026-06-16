"""Fetch real market data → assemble the 市场看板 (体温计 + 板块热力图) via board.py.

I/O lives here; board.py only scores (pure, tested). All numbers fetched from free
sources that work from our hosts (verified 2026-06): multpl (whole-market P/E history),
SSGA SPY holdings xlsx (concentration), yfinance sector ETFs + SPY/RSP (relative strength
+ equal/cap breadth proxy), GitHub S&P 500 constituents CSV + yfinance batch (breadth).
Every fetch is best-effort: a source that fails is dropped + noted, never faked.

Note: breadth scans ~500 constituents (~45–90s) — fine for the daily-cached snapshot,
not the request path; the endpoint caches 24h.
"""
from __future__ import annotations

import csv as _csv
import io
import re
import urllib.request

import board
import market_cycle as _mc   # reuse _http (text), _pct_rank, cape

BOARD_SCHEMA = 1
_CONSTITUENTS_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"
_SSGA_URL = ("https://www.ssga.com/us/en/institutional/library-content/products/fund-data/"
             "etfs/us/holdings-daily-us-en-spy.xlsx")

# sector ETF → 中文名. SMH (semis) is a tech subset but tracked separately (Lucas asked
# about 半导体 specifically).
SECTORS = {
    "XLK": "科技", "SMH": "半导体", "XLC": "通信", "XLY": "可选消费", "XLP": "必需消费",
    "XLV": "医疗", "XLF": "金融", "XLI": "工业", "XLE": "能源", "XLB": "材料",
    "XLU": "公用事业", "XLRE": "房地产",
}


def _bytes(url: str, timeout: int = 40) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": _mc._UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _multpl_pct(slug: str) -> dict | None:
    """Current value + percentile vs full monthly history for a multpl series."""
    try:
        html = _mc._http(f"https://www.multpl.com/{slug}/table/by-month")
        vals = [float(x) for x in re.findall(r"<td>\s*(?:&#x2002;)?\s*(\d+\.\d+)\s*</td>", html)]
        vals = [v for v in vals if 0 < v < 1000]
        if not vals:
            return None
        return {"value": round(vals[0], 1), "percentile": _mc._pct_rank(vals[0], vals)}
    except Exception:  # noqa: BLE001
        return None


def valuation() -> dict:
    """市场估值体温计: S&P 500 P/E percentile + CAPE percentile (whole-market)."""
    pe = _multpl_pct("s-p-500-pe-ratio")
    cp = _mc.cape()   # Shiller CAPE + percentile (reused)
    g = board.valuation_gauge(pe.get("percentile") if pe else None,
                              cp.get("percentile") if cp else None)
    g["pe"] = pe
    g["cape"] = cp
    return g


def ssga_concentration() -> tuple:
    """(top-7 weight %, Herfindahl) from the official SPY daily holdings xlsx."""
    try:
        import pandas as pd
        df = pd.read_excel(io.BytesIO(_bytes(_SSGA_URL)), engine="openpyxl", header=None)
        hdr = None
        for i in range(min(12, len(df))):
            row = [str(x).strip() for x in df.iloc[i].values]
            if "Weight" in row and "Ticker" in row:
                hdr, cols = i, row
                break
        if hdr is None:
            return None, None
        wcol = cols.index("Weight")
        weights = []
        for j in range(hdr + 1, len(df)):
            try:
                w = float(df.iloc[j, wcol])
            except (TypeError, ValueError):
                continue
            if 0 < w < 100:
                weights.append(w)
        if not weights:
            return None, None
        weights.sort(reverse=True)
        top7 = round(sum(weights[:7]), 2) if len(weights) >= 7 else None
        return top7, board.herfindahl(weights)
    except Exception:  # noqa: BLE001
        return None, None


def _rel(series, spy, n: int) -> float | None:
    """Excess return of `series` vs SPY over the last n trading days (decimal)."""
    try:
        if len(series) <= n or len(spy) <= n:
            return None
        return (float(series.iloc[-1]) / float(series.iloc[-1 - n])) / \
               (float(spy.iloc[-1]) / float(spy.iloc[-1 - n])) - 1
    except Exception:  # noqa: BLE001
        return None


def sectors_and_rsp() -> tuple:
    """(sorted sector-heat list, RSP/SPY percentile). One yfinance batch."""
    try:
        import yfinance as yf
        tks = ["SPY", "RSP"] + list(SECTORS)
        d = yf.download(tks, period="1y", progress=False)["Close"].dropna()
        if d is None or d.empty or "SPY" not in d:
            return [], None
        spy = d["SPY"]
        rows = []
        for tk, name in SECTORS.items():
            if tk not in d:
                continue
            heat = board.sector_heat(_rel(d[tk], spy, 126), _rel(d[tk], spy, 63))
            rows.append({"ticker": tk, "name": name, **heat})
        rows.sort(key=lambda r: (r["heat"] is None, -(r["heat"] or 0)))
        rsp_pct = None
        if "RSP" in d:
            ratio = (d["RSP"] / spy).dropna().tolist()
            if len(ratio) >= 30:
                rsp_pct = _mc._pct_rank(ratio[-1], ratio)
        return rows, rsp_pct
    except Exception:  # noqa: BLE001
        return [], None


def breadth() -> dict | None:
    """% of S&P 500 constituents above their 200/50-day MA (chunked yfinance batch)."""
    try:
        txt = _mc._http(_CONSTITUENTS_URL)
        syms = [r["Symbol"].replace(".", "-") for r in _csv.DictReader(io.StringIO(txt)) if r.get("Symbol")]
        if not syms:
            return None
        import yfinance as yf
        a200 = t200 = a50 = t50 = 0
        for i in range(0, len(syms), 100):
            chunk = syms[i:i + 100]
            try:
                dd = yf.download(chunk, period="1y", progress=False)["Close"]
            except Exception:  # noqa: BLE001
                continue
            for s in chunk:
                try:
                    ser = dd[s].dropna()
                except Exception:  # noqa: BLE001
                    continue
                if len(ser) >= 200:
                    t200 += 1
                    a200 += 1 if float(ser.iloc[-1]) > float(ser.tail(200).mean()) else 0
                if len(ser) >= 50:
                    t50 += 1
                    a50 += 1 if float(ser.iloc[-1]) > float(ser.tail(50).mean()) else 0
        if t200 < 50:
            return None
        return {"above_200": round(a200 / t200 * 100, 1),
                "above_50": (round(a50 / t50 * 100, 1) if t50 else None), "n": t200}
    except Exception:  # noqa: BLE001
        return None


def us_board() -> dict:
    """Full 市场看板 snapshot: 3 体温计 (估值/集中度/广度) + 板块热力 list."""
    warnings: list[str] = []
    val = valuation()
    if val.get("percentile") is None:
        warnings.append("全市场估值分位缺失")

    top7, hhi = ssga_concentration()
    secs, rsp_pct = sectors_and_rsp()
    conc = board.concentration_gauge(top7, hhi, rsp_pct)
    if conc.get("label") == "数据缺失":
        warnings.append("集中度数据缺失")
    if not secs:
        warnings.append("板块相对强度数据缺失")

    bd = breadth()
    bg = board.breadth_gauge(bd.get("above_200") if bd else None, bd.get("above_50") if bd else None)
    if bg.get("level") is None:
        warnings.append("市场广度数据缺失")

    temp = board.market_temperature(val, bg, conc)
    return {
        "_schema": BOARD_SCHEMA,
        "market": "美股",
        "temperature": temp,
        "valuation": val,
        "concentration": conc,
        "breadth": {**bg, "n": (bd.get("n") if bd else None)},
        "sectors": secs,
        "crowding_note": "拥挤=估值分位×相对强度×集中度的代理，非实测机构仓位。",
        "warnings": warnings,
    }
