"""A股 市场快照 — 估值分位 + 利率政策 + 两融情绪 (akshare).

China's top-down read differs from the US: it's policy/credit-driven, so the
"future" leg here is the policy/liquidity stance (LPR direction + M1/M2 + PMI),
not a dot plot. All numbers fetched here; reused board.valuation_gauge for the
valuation label. Best-effort: a source that fails is dropped + noted.

⚠️ akshare ordering varies per function — handled explicitly (verified 2026-06):
  stock_index_pe_lg / bond_zh_us_rate / macro_china_lpr = ascending (latest = last);
  macro_china_money_supply = descending (latest = first); margin/PMI = sort by date.
"""
from __future__ import annotations

import board
import market_cycle as _mc   # reuse _pct_rank

CN_SCHEMA = 1


def _f(v):
    try:
        x = float(v)
        return None if x != x else x
    except (TypeError, ValueError):
        return None


def cn_valuation() -> dict:
    """沪深300 滚动市盈率 (TTM P/E) + 历史分位."""
    try:
        import akshare as ak
        df = ak.stock_index_pe_lg(symbol="沪深300")
        col = "滚动市盈率" if "滚动市盈率" in df.columns else "静态市盈率"
        s = [x for x in (_f(v) for v in df[col].tolist()) if x is not None and x > 0]
        if not s:
            return {}
        cur = s[-1]                          # ascending → latest is last
        pct = _mc._pct_rank(cur, s)
        g = board.valuation_gauge(pct, None)
        return {"index": "沪深300", "pe": round(cur, 1), "percentile": pct,
                "label": g["label"], "level": g["level"], "note": g["note"]}
    except Exception:  # noqa: BLE001
        return {}


def cn_rates() -> dict:
    """利率政策：中债 10Y/曲线 + LPR + M1/M2 同比 + 官方 PMI（policy/credit 立场）。"""
    out = {"policy_rates": [], "warnings": []}
    try:
        import akshare as ak
        b = ak.bond_zh_us_rate()
        ty = b["中国国债收益率10年"].dropna()
        if len(ty):
            out["ten_year"] = round(float(ty.iloc[-1]), 2)
        sp = b.get("中国国债收益率10年-2年")
        if sp is not None and len(sp.dropna()):
            out["curve_slope"] = round(float(sp.dropna().iloc[-1]), 2)
    except Exception:  # noqa: BLE001
        out["warnings"].append("中债收益率缺失")
    try:
        import akshare as ak
        lpr = ak.macro_china_lpr()
        l1 = lpr["LPR1Y"].dropna(); l5 = lpr["LPR5Y"].dropna()
        v1 = round(float(l1.iloc[-1]), 2) if len(l1) else None
        v5 = round(float(l5.iloc[-1]), 2) if len(l5) else None
        if v1 is not None:
            out["policy_rates"].append({"name": "🇨🇳 LPR", "value": f"1Y {v1:.2f}%" + (f" · 5Y {v5:.2f}%" if v5 else "")})
        out["lpr_1y"] = v1
    except Exception:  # noqa: BLE001
        out["warnings"].append("LPR 缺失")
    if out.get("ten_year") is not None:
        out["policy_rates"].append({"name": "🇨🇳 国债 10Y", "value": f"{out['ten_year']:.2f}%"
                                    + (f"（10Y-2Y {out['curve_slope']:+.2f}）" if out.get("curve_slope") is not None else "")})
    try:
        import akshare as ak
        ms = ak.macro_china_money_supply()        # descending → latest is first
        m2 = _f(ms["货币和准货币(M2)-同比增长"].iloc[0])
        m1 = _f(ms["货币(M1)-同比增长"].iloc[0])
        out["m2_yoy"], out["m1_yoy"] = m2, m1
        if m1 is not None and m2 is not None:
            out["m1_m2_gap"] = round(m1 - m2, 1)
    except Exception:  # noqa: BLE001
        out["warnings"].append("M1/M2 缺失")
    try:
        import akshare as ak
        p = ak.macro_china_pmi_yearly()
        p = p[p["商品"].astype(str).str.contains("制造业")] if "商品" in p.columns else p
        p = p.dropna(subset=["今值"]).sort_values("日期")
        if len(p):
            out["pmi"] = round(float(p["今值"].iloc[-1]), 1)
    except Exception:  # noqa: BLE001
        out["warnings"].append("PMI 缺失")
    # policy/credit note
    bits = []
    if out.get("m1_m2_gap") is not None:
        gap = out["m1_m2_gap"]
        bits.append(f"M1-M2 剪刀差 {gap:+.1f}pp（{'资金活化转好' if gap > 0 else '资金活化偏弱'}）")
    if out.get("pmi") is not None:
        bits.append(f"官方制造业 PMI {out['pmi']}（{'扩张' if out['pmi'] >= 50 else '收缩'}）")
    out["note"] = "；".join(bits)
    return out


def cn_sentiment() -> dict | None:
    """两融余额 + 近 ~20 交易日趋势（情绪/杠杆温度）。"""
    try:
        import akshare as ak
        from datetime import datetime, date
        df = ak.stock_margin_sse()
        date_col = "信用交易日期"
        col = "融资融券余额" if "融资融券余额" in df.columns else "融资余额"
        df = df.dropna(subset=[col]).sort_values(date_col)     # ascending after sort
        vals = [x for x in (_f(v) for v in df[col].tolist()) if x is not None]
        last_date = str(df[date_col].iloc[-1])
        # staleness guard: SSE margin endpoint via akshare is flaky; drop if >30d old
        try:
            if (date.today() - datetime.strptime(last_date[:8], "%Y%m%d").date()).days > 30:
                return None
        except ValueError:
            return None
        if len(vals) < 22:
            return None
        now, prev = vals[-1], vals[-22]
        trend = round((now / prev - 1) * 100, 1) if prev else None
        return {"margin_balance_yi": round(now / 1e8, 0), "trend_20d_pct": trend,
                "as_of": last_date,
                "note": ("两融余额近月" + ("回升（杠杆情绪转暖）" if (trend or 0) > 1 else "回落（去杠杆）" if (trend or 0) < -1 else "基本持平"))}
    except Exception:  # noqa: BLE001
        return None


def cn_market() -> dict:
    val = cn_valuation()
    rt = cn_rates()
    sent = cn_sentiment()
    warnings = list(rt.get("warnings") or [])
    if not val:
        warnings.append("沪深300 估值分位缺失")
    if sent is None:
        warnings.append("两融情绪缺失")
    return {
        "_schema": CN_SCHEMA, "market": "A股",
        "valuation": val,
        "rates": {k: v for k, v in rt.items() if k != "warnings"},
        "sentiment": sent or {},
        "note": "A股自上而下：估值分位 + 政策/信用立场(LPR/M1M2/PMI) + 两融情绪。中国周期政策驱动、信用脉冲领先。",
        "warnings": warnings,
    }
