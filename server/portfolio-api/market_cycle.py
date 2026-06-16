"""Fetch real market data → assemble the US CYCLE compass (周期罗盘) via cycle.py.

Division of labour matches the rest of the engine: *this* module does all the I/O
(pull real numbers), `cycle.py` only scores them — the AI never sources or invents.

Keyless core (always works from our hosts):
  - yield curve 10Y–3M  → reuse market_data.macro_env (yfinance ^TNX/^IRX)
  - VIX term structure   → yfinance ^VIX / ^VIX3M
  - CAPE + percentile    → multpl.com (full monthly history)

Optional FRED layer (lights up when VI_FRED_API_KEY is set; the keyless `fredgraph`
host is blocked from our server, but the API host api.stlouisfed.org works with a
free key):
  - HY credit spread OAS + percentile (BAMLH0A0HYM2)
  - Fed net liquidity 4-week slope (WALCL − TGA − RRP)
  - Sahm recession rule (SAHMREALTIME)  ·  M2 YoY (M2SL)

Every fetch is best-effort: a source that fails is simply dropped (with a warning),
never faked. cycle.composite_cycle blends whatever lenses came back.
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

import cycle
import market_data as _md

CYCLE_SCHEMA = 1
_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36")
_FRED_KEY = os.environ.get("VI_FRED_API_KEY", "").strip()
_FRED_API = "https://api.stlouisfed.org/fred/series/observations"


def _http(url: str, timeout: int = 25) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _pct_rank(value, history) -> float | None:
    """Percentile of `value` within `history` (0=cheapest/lowest, 100=highest).
    Needs ≥30 points to be meaningful (mirrors market_data._percentile)."""
    hist = [h for h in history if h is not None]
    if value is None or len(hist) < 30:
        return None
    below = sum(1 for h in hist if h <= value)
    return round(below / len(hist) * 100, 1)


# --------------------------------------------------------------------------- #
# Keyless sources
# --------------------------------------------------------------------------- #

def vix_term_structure() -> dict | None:
    """IVTS = VIX / VIX3M. <1 contango (calm), >1 backwardation (near-term fear)."""
    try:
        import yfinance as yf
        d = yf.download(["^VIX", "^VIX3M"], period="6d", progress=False)["Close"].dropna()
        if d is None or d.empty:
            return None
        vix = float(d["^VIX"].iloc[-1])
        vix3m = float(d["^VIX3M"].iloc[-1])
        if vix3m <= 0:
            return None
        return {"vix": round(vix, 2), "vix3m": round(vix3m, 2), "ivts": round(vix / vix3m, 3)}
    except Exception:  # noqa: BLE001
        return None


def cape() -> dict | None:
    """Shiller CAPE current value + percentile vs full monthly history (multpl)."""
    try:
        html = _http("https://www.multpl.com/shiller-pe/table/by-month")
        # value cells look like: <td>\n &#x2002;\n 42.18\n</td>  (date cells don't)
        vals = [float(x) for x in re.findall(r"<td>\s*(?:&#x2002;)?\s*(\d+\.\d+)\s*</td>", html)]
        vals = [v for v in vals if 1 < v < 200]
        if not vals:
            return None
        current = vals[0]   # table is newest-first
        return {"value": round(current, 1), "percentile": _pct_rank(current, vals)}
    except Exception:  # noqa: BLE001
        return None


# --------------------------------------------------------------------------- #
# Optional FRED layer (free API key)
# --------------------------------------------------------------------------- #

def _fred(series_id: str, limit: int = 100000, sort: str = "asc") -> list | None:
    if not _FRED_KEY:
        return None
    url = (f"{_FRED_API}?series_id={series_id}&api_key={_FRED_KEY}&file_type=json"
           f"&sort_order={sort}&limit={limit}")
    try:
        data = json.loads(_http(url))
        out = []
        for o in data.get("observations", []):
            v = o.get("value")
            if v not in (".", "", None):
                try:
                    out.append((o.get("date"), float(v)))
                except ValueError:
                    pass
        return out or None
    except Exception:  # noqa: BLE001
        return None


def hy_spread() -> dict | None:
    obs = _fred("BAMLH0A0HYM2")
    if not obs:
        return None
    vals = [v for _, v in obs]
    return {"value": round(vals[-1], 2), "percentile": _pct_rank(vals[-1], vals)}


def m2_yoy() -> float | None:
    obs = _fred("M2SL", limit=14, sort="desc")
    if not obs or len(obs) < 13:
        return None
    latest = obs[0][1]
    year_ago = obs[12][1]
    if year_ago:
        return round((latest / year_ago - 1) * 100, 1)
    return None


def sahm() -> float | None:
    obs = _fred("SAHMREALTIME", limit=1, sort="desc")
    return round(obs[0][1], 2) if obs else None


def net_liquidity_slope() -> float | None:
    """Fed net liquidity = WALCL(millions→/1000) − TGA(WTREGEN, $bn) − RRP(RRPONTSYD,
    $bn). Two-point ~4-week % slope (positive = liquidity expanding)."""
    walcl = _fred("WALCL", limit=8, sort="desc")
    tga = _fred("WTREGEN", limit=8, sort="desc")
    rrp = _fred("RRPONTSYD", limit=40, sort="desc")
    if not walcl or not tga or not rrp:
        return None

    def _net(i_w, i_t, i_r):
        return walcl[i_w][1] / 1000.0 - tga[i_t][1] - rrp[i_r][1]

    try:
        now = _net(0, 0, 0)
        prev = _net(min(4, len(walcl) - 1), min(4, len(tga) - 1), min(20, len(rrp) - 1))
        if prev:
            return round((now - prev) / abs(prev) * 100, 1)
    except Exception:  # noqa: BLE001
        return None
    return None


# --------------------------------------------------------------------------- #
# Assemble
# --------------------------------------------------------------------------- #

def us_cycle() -> dict:
    """Full US cycle compass snapshot: lenses → composite position → asset tilt +
    the CAPE return-cap flag. Best-effort; missing lenses are noted, not faked."""
    warnings: list[str] = []

    # 1) yield curve 10Y-3M (reuse the already-normalized macro env)
    env = _md.macro_env("美股") or {}
    t10y3m = env.get("curve_slope")
    rec_prob = cycle.recession_prob_from_curve(t10y3m)
    yc = cycle.yield_curve_lens(t10y3m, rec_prob)
    if yc is None:
        warnings.append("收益率曲线数据缺失")

    # 2) VIX term structure
    vix = vix_term_structure()
    vol = cycle.volatility_lens(vix["ivts"]) if vix else None
    if vol is None:
        warnings.append("VIX 期限结构缺失")

    # 3) CAPE percentile (valuation)
    cp = cape()
    val = cycle.valuation_lens(cp.get("percentile"), cp.get("value")) if cp else None
    cape_pct = cp.get("percentile") if cp else None
    if val is None:
        warnings.append("CAPE 估值分位缺失")

    # 4) optional FRED layer
    hy = hy_spread() if _FRED_KEY else None
    cr = cycle.credit_lens(hy.get("percentile"), hy.get("value")) if hy else None
    nls = net_liquidity_slope() if _FRED_KEY else None
    m2 = m2_yoy() if _FRED_KEY else None
    liq = cycle.liquidity_lens(nls, m2)
    sahm_v = sahm() if _FRED_KEY else None
    if not _FRED_KEY:
        warnings.append("未配置 VI_FRED_API_KEY：信用/流动性/Sahm 透镜暂缺（接入免费 FRED key 即点亮）")

    lenses = {"yield_curve": yc, "credit": cr, "liquidity": liq, "valuation": val, "volatility": vol}
    comp = cycle.composite_cycle(lenses, sahm=sahm_v)
    flag_on, flag_note = cycle.cape_discount_flag(cape_pct)

    # ordered lens list for display
    titles = {"yield_curve": "利率/衰退", "credit": "信用", "liquidity": "流动性",
              "valuation": "估值", "volatility": "波动/情绪"}
    lens_list = []
    for key in ("yield_curve", "credit", "liquidity", "valuation", "volatility"):
        ln = lenses.get(key)
        lens_list.append({
            "key": key, "title": titles[key],
            "score": ln[0] if ln else None,
            "label": ln[1] if ln else "数据缺失",
            "detail": ln[2] if ln else "",
        })

    return {
        "_schema": CYCLE_SCHEMA,
        "market": "美股",
        "composite": comp,
        "lenses": lens_list,
        "asset_tilt": cycle.asset_tilt(comp["level"]),
        "cape_flag": {"on": flag_on, "note": flag_note},
        "recession_prob": round(rec_prob * 100, 1) if rec_prob is not None else None,
        "fred_enabled": bool(_FRED_KEY),
        "warnings": warnings,
    }
