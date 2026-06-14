"""Real market-data layer for the 公司分析 (company analysis) dashboard.

Gives the analysis page a factual spine: instead of an AI report with no numbers,
we fetch real fundamentals, financial-statement time-series, price history, news,
and primary-source SEC filings — which the frontend renders as charts + a 消息流,
and (later) we will feed into the hermes prompt so it reasons on real data.

Sources (all free, no key required):
  US (美股):
    - yfinance .......... quote, profile, statements, price, news (Apache-2.0)
    - SEC EDGAR REST .... primary-source filings (10-K/10-Q/8-K/13F), official
    - Google News RSS ... news fallback when yfinance .news is empty
  A-share (A股) via akshare (MIT):
    - stock_value_em ........................ price / market cap / PE / PB / PS
    - stock_financial_abstract .............. revenue/profit trend + ratios (ROE/margins/growth/debt)
    - stock_zh_a_hist ....................... monthly price history
    - stock_news_em ......................... 东方财富 per-stock news
    - stock_zh_a_disclosure_report_cninfo ... 巨潮 official announcements (primary source)

Design rules:
  - Never raise to the caller for missing fields — degrade gracefully and collect
    a `warnings` list. A partial dashboard beats a 500.
  - No fabrication: a field we cannot fetch is `null`, never guessed.
  - yfinance / akshare are imported lazily so the module (and app.py) load even if
    they aren't installed; endpoints then return a clean "数据源未安装" error.
  - akshare scrapes Chinese sites that intermittently drop connections — calls are
    wrapped in `_retry`. Same unified dict shape across markets.
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

import forensics as _fx
import macro as _macro
import valuation as _val

# Identify ourselves to SEC EDGAR (required by their fair-access policy).
SEC_UA = "value-investment-learning lucas.jin@boostengine.ai"
_HTTP_TIMEOUT = 20


# --------------------------------------------------------------------------- #
# small helpers
# --------------------------------------------------------------------------- #

def _num(v):
    """Coerce to a JSON-safe float, mapping NaN/inf/None → None."""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f or f in (float("inf"), float("-inf")):  # NaN / inf
        return None
    return f


def _pct(v):
    """yfinance ratios are decimals (0.23 = 23%). Return as a percentage number."""
    f = _num(v)
    return None if f is None else round(f * 100, 2)


def _http_get(url, headers=None):
    req = urllib.request.Request(url, headers=headers or {"User-Agent": SEC_UA})
    with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as r:
        return r.read()


# --------------------------------------------------------------------------- #
# financial-health radar (the "snowflake")
# --------------------------------------------------------------------------- #

def _band(value, bands, reverse=False):
    """Map a metric to a 0-100 score via ascending (value, score) breakpoints.

    bands: list of (threshold, score) where the FIRST threshold a value is <=
    wins. `reverse=True` for "higher is better" metrics evaluated the same way.
    Returns None if value is None so the axis can show as "数据缺失".
    """
    if value is None:
        return None
    for threshold, score in bands:
        if value <= threshold:
            return score
    return bands[-1][1] if reverse else 0


def _radar(metrics: dict, fin: dict) -> dict:
    """Five-axis financial-health glyph. Transparent, banded heuristics — this is
    a learning aid, not advice. Each axis carries a one-line note explaining it."""
    pe = metrics.get("pe")
    pb = metrics.get("pb")
    net_margin = metrics.get("net_margin")
    roe = metrics.get("roe")
    rev_growth = metrics.get("revenue_growth")
    earn_growth = metrics.get("earnings_growth")
    d2e = metrics.get("debt_to_equity")
    current_ratio = metrics.get("current_ratio")

    # 估值 value: lower P/E + P/B → cheaper → higher score (lower is better)
    pe_s = _band(pe, [(10, 90), (15, 78), (20, 65), (30, 48), (45, 30), (1e9, 15)])
    pb_s = _band(pb, [(1, 90), (2, 78), (4, 62), (7, 42), (1e9, 22)])
    value = _avg([pe_s, pb_s])

    # 盈利能力 profitability: net margin + ROE (higher is better)
    nm_s = _band(net_margin, [(0, 15), (5, 45), (10, 62), (20, 80), (1e9, 92)])
    roe_s = _band(roe, [(0, 15), (8, 45), (15, 68), (25, 85), (1e9, 95)])
    profit = _avg([nm_s, roe_s])

    # 成长 growth: revenue + earnings growth (%)
    rg_s = _band(rev_growth, [(0, 20), (5, 45), (12, 68), (25, 85), (1e9, 95)])
    eg_s = _band(earn_growth, [(0, 20), (8, 50), (20, 72), (40, 88), (1e9, 95)])
    growth = _avg([rg_s, eg_s])

    # 财务健康 balance-sheet health: debt/equity (lower better) + current ratio
    # yfinance debtToEquity is a percentage (e.g. 150 = 1.5x).
    de_s = _band(d2e, [(30, 92), (60, 78), (100, 60), (180, 40), (1e9, 20)])
    cr_s = _band(current_ratio, [(1, 35), (1.5, 65), (2.5, 88), (1e9, 80)])
    health = _avg([de_s, cr_s])

    # 现金流 cash quality: FCF positive & sizeable vs revenue
    fcf = fin.get("fcf") or []
    rev = fin.get("revenue") or []
    cash = None
    if fcf and rev and fcf[-1] is not None and rev[-1]:
        fcf_margin = fcf[-1] / rev[-1] * 100
        cash = _band(fcf_margin, [(0, 15), (5, 50), (10, 70), (20, 88), (1e9, 95)])

    axes = [
        ("估值", value, "P/E、P/B 越低分越高（越便宜）；高分≠该买，要配合质量看"),
        ("盈利能力", profit, "净利率 + ROE：赚钱效率"),
        ("成长", growth, "营收 + 盈利增速"),
        ("财务健康", health, "负债率（越低越好）+ 流动比率：抗风险能力"),
        ("现金流", cash, "自由现金流占营收比：利润是否变成真金白银"),
    ]
    return {
        "indicators": [{"name": n, "max": 100} for n, _, _ in axes],
        "values": [None if s is None else round(s) for _, s, _ in axes],
        "notes": {n: note for n, _, note in axes},
    }


def _avg(xs):
    xs = [x for x in xs if x is not None]
    return round(sum(xs) / len(xs)) if xs else None


def _percentile(values, current, positive_only=True):
    """Percentile rank of `current` within history (0 = cheapest ever, 100 = dearest).

    For valuation (P/E, P/B) a LOW percentile = historically cheap — the 0-25%
    'cheap zone' the methodology cares about. Needs ≥30 points to be meaningful.
    """
    cur = _num(current)
    if cur is None:
        return None
    xs = [v for v in (_num(x) for x in values) if v is not None and (v > 0 if positive_only else True)]
    if len(xs) < 30:
        return None
    below = sum(1 for x in xs if x <= cur)
    return round(below / len(xs) * 100)


# --------------------------------------------------------------------------- #
# yfinance extraction
# --------------------------------------------------------------------------- #

def _row(df, *names):
    """Pull a statement row (ascending by year) by trying several label aliases."""
    if df is None or getattr(df, "empty", True):
        return None
    for name in names:
        if name in df.index:
            series = df.loc[name]
            # yfinance columns are timestamps, newest first → reverse to oldest first
            return [_num(v) for v in series[::-1].tolist()]
    return None


def _ratio_series(numer, denom):
    if not numer or not denom:
        return None
    out = []
    for a, b in zip(numer, denom):
        out.append(round(a / b * 100, 2) if (a is not None and b) else None)
    return out


def _financials(t) -> dict:
    """Annual statement time-series, oldest→newest, last ~6 years."""
    inc = getattr(t, "income_stmt", None)
    cf = getattr(t, "cashflow", None)

    years = []
    if inc is not None and not getattr(inc, "empty", True):
        years = [str(c.year) for c in inc.columns[::-1]]

    revenue = _row(inc, "Total Revenue", "TotalRevenue")
    net_income = _row(inc, "Net Income", "NetIncome", "Net Income Common Stockholders")
    gross_profit = _row(inc, "Gross Profit", "GrossProfit")
    operating_income = _row(inc, "Operating Income", "OperatingIncome", "EBIT")
    eps = _row(inc, "Diluted EPS", "Basic EPS")

    fcf = _row(cf, "Free Cash Flow", "FreeCashFlow")
    if fcf is None:
        ocf = _row(cf, "Operating Cash Flow", "Cash Flow From Continuing Operating Activities")
        capex = _row(cf, "Capital Expenditure", "CapitalExpenditure")
        if ocf and capex:
            fcf = [(o + c) if (o is not None and c is not None) else None
                   for o, c in zip(ocf, capex)]  # capex is negative in yfinance

    n = len(years)

    def fit(xs):
        return (xs or [None] * n)[-6:]

    years = years[-6:]
    return {
        "years": years,
        "revenue": fit(revenue),
        "net_income": fit(net_income),
        "gross_profit": fit(gross_profit),
        "operating_income": fit(operating_income),
        "eps": fit(eps),
        "fcf": fit(fcf),
        "gross_margin": fit(_ratio_series(gross_profit, revenue)),
        "operating_margin": fit(_ratio_series(operating_income, revenue)),
        "net_margin": fit(_ratio_series(net_income, revenue)),
    }


def _price_history(t) -> dict:
    """~5y monthly OHLC for a clean candlestick / line chart."""
    try:
        h = t.history(period="5y", interval="1mo")
    except Exception:
        return {"dates": [], "ohlc": [], "close": []}
    if h is None or h.empty:
        return {"dates": [], "ohlc": [], "close": []}
    dates, ohlc, close = [], [], []
    for idx, r in h.iterrows():
        o, hi, lo, c = _num(r.get("Open")), _num(r.get("High")), _num(r.get("Low")), _num(r.get("Close"))
        if c is None:
            continue
        dates.append(idx.strftime("%Y-%m"))
        ohlc.append([o, c, lo, hi])  # ECharts candlestick order: [open, close, low, high]
        close.append(c)
    return {"dates": dates, "ohlc": ohlc, "close": close}


def _peer_metrics(info, ticker=None):
    """Comparable metrics for one company, from a yfinance .info dict."""
    ev = _num(info.get("enterpriseValue"))
    ebitda = _num(info.get("ebitda"))
    return {
        "ticker": ticker or info.get("symbol"),
        "name": info.get("shortName") or info.get("longName") or ticker,
        "market_cap": _num(info.get("marketCap")),
        "pe": _num(info.get("trailingPE")),
        "pb": _num(info.get("priceToBook")),
        "ps": _num(info.get("priceToSalesTrailing12Months")),
        "ev_ebitda": round(ev / ebitda, 1) if (ev and ebitda and ebitda > 0) else None,
        "roe": _pct(info.get("returnOnEquity")),
        "gross_margin": _pct(info.get("grossMargins")),
        "net_margin": _pct(info.get("profitMargins")),
        "revenue_growth": _pct(info.get("revenueGrowth")),
    }


def _rank_pctile(rows, key, value):
    """Percentile of `value` among peers' `key` (0 = lowest in the set). ≥3 needed."""
    xs = [r[key] for r in rows if r.get(key) is not None]
    if value is None or len(xs) < 3:
        return None
    return round(sum(1 for x in xs if x <= value) / len(xs) * 100)


def peer_verdict_and_flag(rows, percentiles):
    """Tool ③ EV/EBITDA peer verdict (cheapest 30% AND ROE not below peer median) +
    a 错杀/高估 mispricing flag. Pure — separated so it's unit-testable."""
    evp = percentiles.get("ev_ebitda")
    self_row = next((r for r in rows if r.get("is_self")), rows[0] if rows else {})
    roes = sorted(r["roe"] for r in rows if r.get("roe") is not None)
    roe_med = roes[len(roes) // 2] if roes else None
    roe_ok = self_row.get("roe") is not None and roe_med is not None and self_row["roe"] >= roe_med
    if evp is None:
        verdict = "数据缺失"
    elif evp <= 30 and roe_ok:
        verdict = "便宜（同行最便宜30%且ROE不输）"
    elif evp >= 70:
        verdict = "偏贵（同行偏贵端）"
    else:
        verdict = "合理（同行中段）"

    val_p = [percentiles[k] for k in ("ev_ebitda", "pe") if percentiles.get(k) is not None]
    q_p = [percentiles[k] for k in ("roe", "gross_margin", "net_margin") if percentiles.get(k) is not None]
    flag = None
    if val_p and q_p:
        cheap, rich = min(val_p) <= 35, min(val_p) >= 65
        hi_q = (percentiles.get("roe") or 0) >= 55 and max(q_p) >= 50
        lo_q = (percentiles.get("roe") or 100) <= 45
        if cheap and hi_q:
            flag = "潜在错杀：比同行便宜，但质量（ROE/利润率）更高"
        elif rich and lo_q:
            flag = "潜在高估：比同行贵，但质量更差"
        else:
            flag = "与同行大致匹配，无明显错价"
    return verdict, flag


def peer_comparison(ticker, market, max_peers=8):
    """Industry peer comparison. US via yfinance Industry; A-share not wired yet."""
    ticker = (ticker or "").strip().upper()
    out = {"ticker": ticker, "market": market, "industry": None, "rows": [],
           "percentiles": {}, "ev_ebit_verdict": "数据缺失", "mispricing": None, "warnings": []}
    if not _is_us(market):
        out["warnings"].append("同行对比暂仅支持美股（A股同行数据待接入）。")
        return out
    try:
        import yfinance as yf
    except ImportError:
        out["warnings"].append("服务器未安装 yfinance。")
        return out
    try:
        t = yf.Ticker(ticker)
        info = t.info or {}
        out["industry"] = info.get("industry")
        symbols = []
        if info.get("industryKey"):
            try:
                tc = yf.Industry(info["industryKey"]).top_companies
                if tc is not None and not getattr(tc, "empty", True):
                    symbols = [str(s).upper() for s in tc.index.tolist()]
            except Exception:  # noqa: BLE001
                pass
        symbols = [s for s in symbols if s != ticker][:max_peers]
        if not symbols:
            out["warnings"].append("未找到同行（行业样本稀疏或分类过窄）。")
            return out
        rows = [{**_peer_metrics(info, ticker), "is_self": True}]
        for s in symbols:
            try:
                rows.append({**_peer_metrics(yf.Ticker(s).info or {}, s), "is_self": False})
            except Exception:  # noqa: BLE001
                continue
        out["rows"] = rows
        dims = ["pe", "pb", "ps", "ev_ebitda", "roe", "gross_margin", "net_margin", "revenue_growth"]
        out["percentiles"] = {d: _rank_pctile(rows, d, rows[0].get(d)) for d in dims}
        out["ev_ebit_verdict"], out["mispricing"] = peer_verdict_and_flag(rows, out["percentiles"])
    except Exception as e:  # noqa: BLE001
        out["warnings"].append(f"同行对比失败：{str(e)[:120]}")
    return out


def _by_year(pairs):
    """{'YYYY': value} from (col, value) pairs, keeping positive values only."""
    out = {}
    for k, v in pairs:
        val = _num(v)
        if val is not None and val > 0:
            out[str(k)] = val
    return out


def _val_for_year(year, by_year):
    """Value for a fiscal year: exact, else most-recent prior, else earliest available."""
    if not by_year:
        return None
    if year in by_year:
        return by_year[year]
    prior = [y for y in by_year if y <= year]
    return by_year[max(prior)] if prior else by_year[min(by_year)]


def _us_valuation_history(t, info, price_history, financials):
    """Build a monthly P/E & P/B history from data WE fetch (price ÷ annual EPS /
    book-value-per-share, EPS/BVPS stepped by fiscal year), then return the current
    value's percentile. No external/AI data — only yfinance numbers we pulled.

    yfinance gives no ready-made historical-ratio series, so we synthesize one at
    monthly granularity over the ~5y we have annual EPS for (≥30 points → usable).
    """
    closes = price_history.get("close") or []
    dates = price_history.get("dates") or []
    if not closes:
        return {}
    eps_y = _by_year(zip(financials.get("years") or [], financials.get("eps") or []))
    # book value per share by year = total equity / shares outstanding
    bvps_y = {}
    shares = _num(info.get("sharesOutstanding"))
    if shares:
        try:
            bs = getattr(t, "balance_sheet", None)
            if bs is not None and not getattr(bs, "empty", True):
                for name in ("Stockholders Equity", "Total Stockholders Equity",
                             "Stockholder Equity", "Common Stock Equity"):
                    if name in bs.index:
                        bvps_y = _by_year((c.year, v / shares) for c, v in bs.loc[name].items() if _num(v))
                        break
        except Exception:  # noqa: BLE001
            bvps_y = {}

    pe_series, pb_series = [], []
    for d, c in zip(dates, closes):
        yr = d[:4]
        e = _val_for_year(yr, eps_y)
        if e:
            pe_series.append(c / e)
        b = _val_for_year(yr, bvps_y)
        if b:
            pb_series.append(c / b)

    pe_pct = _percentile(pe_series, pe_series[-1]) if len(pe_series) >= 30 else None
    pb_pct = _percentile(pb_series, pb_series[-1]) if len(pb_series) >= 30 else None
    if pe_pct is None and pb_pct is None:
        return {}
    return {
        "pe_percentile": pe_pct, "pb_percentile": pb_pct,
        "span": f"{dates[0]}~{dates[-1]}",
        "method": "美股：股价÷历年EPS/每股净资产 自算的 P/E·P/B 历史分位（年度口径）",
    }


def _yf_news(t, name, ticker):
    """yfinance .news (shape varies by version), with Google News RSS fallback."""
    items = []
    try:
        raw = t.news or []
    except Exception:
        raw = []
    for a in raw[:20]:
        # newer yfinance nests under 'content'; older is flat
        c = a.get("content") if isinstance(a.get("content"), dict) else a
        title = c.get("title") or a.get("title")
        if not title:
            continue
        link = (c.get("canonicalUrl") or {}).get("url") if isinstance(c.get("canonicalUrl"), dict) else None
        link = link or c.get("clickThroughUrl", {}).get("url") if isinstance(c.get("clickThroughUrl"), dict) else link
        link = link or a.get("link") or c.get("link")
        pub = (c.get("provider") or {}).get("displayName") if isinstance(c.get("provider"), dict) else a.get("publisher")
        ts = c.get("pubDate") or c.get("displayTime") or a.get("providerPublishTime")
        items.append({"title": title, "link": link, "publisher": pub or "", "time": _norm_time(ts), "type": "news"})
    if not items:
        items = _google_news(name or ticker)
    return items


def _google_news(query):
    """Free, keyless breadth fallback. Store headline+link only (non-commercial feed)."""
    try:
        q = urllib.parse.quote(f"{query} stock")
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        root = ET.fromstring(_http_get(url, {"User-Agent": "Mozilla/5.0"}))
        out = []
        for item in root.iter("item"):
            title = item.findtext("title")
            if not title:
                continue
            src = item.find("source")
            out.append({
                "title": title,
                "link": item.findtext("link"),
                "publisher": (src.text if src is not None else "") or "",
                "time": _norm_time(item.findtext("pubDate")),
                "type": "news",
            })
            if len(out) >= 15:
                break
        return out
    except Exception:
        return []


def _norm_time(ts):
    if ts is None:
        return None
    try:
        if isinstance(ts, (int, float)):
            return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
        # RFC822 (Google) or ISO (yfinance)
        for fmt in ("%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                return datetime.strptime(ts, fmt).astimezone(timezone.utc).isoformat()
            except ValueError:
                pass
        return str(ts)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# SEC EDGAR — primary-source filings feed
# --------------------------------------------------------------------------- #

_CIK_MAP = None


def _cik_for(ticker):
    global _CIK_MAP
    if _CIK_MAP is None:
        try:
            data = json.loads(_http_get("https://www.sec.gov/files/company_tickers.json"))
            _CIK_MAP = {row["ticker"].upper(): row["cik_str"] for row in data.values()}
        except Exception:
            _CIK_MAP = {}
    return _CIK_MAP.get(ticker.upper())


_FORM_LABELS = {
    "10-K": "年报 10-K", "10-Q": "季报 10-Q", "8-K": "重大事件 8-K",
    "DEF 14A": "委托书 DEF 14A", "13F-HR": "机构持仓 13F", "4": "内部人交易 Form 4",
    "SC 13D": "举牌 13D", "SC 13G": "被动持股 13G",
}


def sec_filings(ticker, limit=12):
    """Recent primary-source filings from SEC EDGAR (US only). Empty list on miss."""
    cik = _cik_for(ticker)
    if not cik:
        return []
    try:
        data = json.loads(_http_get(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json"))
    except Exception:
        return []
    recent = (data.get("filings") or {}).get("recent") or {}
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accns = recent.get("accessionNumber", [])
    docs = recent.get("primaryDocument", [])
    # The meaty filings a value investor wants first; Form 4 (insider trades) is
    # frequent and would otherwise flood the feed, so it's filled in last.
    key = ["10-K", "10-Q", "8-K", "DEF 14A", "13F-HR", "SC 13D", "SC 13G"]
    minor = ["4"]

    def collect(allowed, cap):
        rows = []
        for i, form in enumerate(forms):
            if form not in allowed:
                continue
            accn = accns[i].replace("-", "") if i < len(accns) else ""
            doc = docs[i] if i < len(docs) else ""
            link = (f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accn}/{doc}"
                    if accn and doc else
                    f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={int(cik)}&type={urllib.parse.quote(form)}")
            rows.append({
                "title": _FORM_LABELS.get(form, form), "form": form, "link": link,
                "time": dates[i] if i < len(dates) else None, "type": "filing",
            })
            if len(rows) >= cap:
                break
        return rows

    out = collect(key, limit)
    if len(out) < limit:
        out += collect(minor, limit - len(out))
    return out


# --------------------------------------------------------------------------- #
# A-share (akshare) — same dict shape as US, different data source
# --------------------------------------------------------------------------- #

def _is_us(market):
    return (market or "").strip() in ("", "美股", "US", "us")


def _is_cn(market):
    return (market or "").strip() in ("A股", "沪深", "沪深京", "CN", "cn")


def _cn_code(ticker):
    """Normalize an A-share ticker to the bare 6-digit code (strip sh/sz, .SS/.SZ)."""
    m = re.search(r"\d{6}", ticker or "")
    return m.group(0) if m else (ticker or "").strip()


def _retry(fn, tries=3):
    """akshare scrapes Chinese sites that intermittently drop connections — retry."""
    import time
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(0.6 * (i + 1))
    raise last


_RF_DEFAULT = {"US": 0.043, "CN": 0.023}  # fallback 10Y if the live fetch fails


def ten_year_yield(market):
    """Risk-free 10Y govt-bond yield (decimal) for the OE-yield-vs-10Y tool."""
    if _is_us(market):
        try:
            import yfinance as yf
            h = yf.Ticker("^TNX").history(period="5d")
            if h is not None and not h.empty:
                v = float(h["Close"].dropna().iloc[-1])
                if v > 20:        # older ^TNX feeds quoted 10×yield
                    v /= 10
                if 0.3 <= v <= 8:
                    return round(v / 100, 4)
        except Exception:  # noqa: BLE001
            pass
        return _RF_DEFAULT["US"]
    if _is_cn(market):
        try:
            import akshare as ak
            df = _retry(lambda: ak.bond_zh_us_rate())
            for col in ("中国国债收益率10年",):
                if df is not None and col in df.columns:
                    s = df[col].dropna()
                    if len(s):
                        v = float(s.iloc[-1])
                        if 0.3 <= v <= 8:
                            return round(v / 100, 4)
        except Exception:  # noqa: BLE001
            pass
        return _RF_DEFAULT["CN"]
    return None


def _norm_yield(v):
    v = _num(v)
    if v is None:
        return None
    if v > 20:        # some feeds quote 10×yield
        v /= 10
    return round(v, 2) if 0 <= v <= 20 else None


def macro_env(market):
    """Macro-environment snapshot (market-level): rates level/trend + yield-curve
    state (+ A股 LPR). All best-effort; missing pieces are simply omitted."""
    env = {}
    if _is_us(market):
        try:
            import yfinance as yf
            h = yf.Ticker("^TNX").history(period="1y")
            cl = h["Close"].dropna() if (h is not None and not h.empty) else None
            if cl is not None and len(cl):
                now, ago = _norm_yield(cl.iloc[-1]), _norm_yield(cl.iloc[0])
                if now is not None:
                    env["ten_year"] = now
                if ago is not None:
                    env["ten_year_1y_ago"] = ago
                    env["rate_trend"] = _macro.rate_trend(now, ago)
        except Exception:  # noqa: BLE001
            pass
        try:
            import yfinance as yf
            s = yf.Ticker("^IRX").history(period="5d")
            sc = s["Close"].dropna() if (s is not None and not s.empty) else None
            if sc is not None and len(sc):
                short = _norm_yield(sc.iloc[-1])
                if short is not None:
                    env["short_rate"] = short
                    if env.get("ten_year") is not None:
                        env["curve_slope"] = round(env["ten_year"] - short, 2)
                        env["curve_state"] = _macro.curve_state(env["curve_slope"])
        except Exception:  # noqa: BLE001
            pass
        return env
    if _is_cn(market):
        try:
            import akshare as ak
            df = _retry(lambda: ak.bond_zh_us_rate())
            if df is not None and "中国国债收益率10年" in df.columns:
                s = df["中国国债收益率10年"].dropna()
                if len(s):
                    env["ten_year"] = round(float(s.iloc[-1]), 2)
                    if len(s) > 240:
                        env["ten_year_1y_ago"] = round(float(s.iloc[-240]), 2)
                        env["rate_trend"] = _macro.rate_trend(env["ten_year"], env["ten_year_1y_ago"])
                sp = df.get("中国国债收益率10年-2年")
                if sp is not None and len(sp.dropna()):
                    env["curve_slope"] = round(float(sp.dropna().iloc[-1]), 2)
                    env["curve_state"] = _macro.curve_state(env["curve_slope"])
        except Exception:  # noqa: BLE001
            pass
        try:
            import akshare as ak
            lpr = _retry(lambda: ak.macro_china_lpr())
            if lpr is not None and "LPR1Y" in lpr.columns:
                v = lpr["LPR1Y"].dropna()
                if len(v):
                    env["lpr_1y"] = round(float(v.iloc[-1]), 2)
        except Exception:  # noqa: BLE001
            pass
        return env
    return env


def _cn_prefix(code):
    if code[:1] in ("6", "9"):
        return "sh"
    if code[:1] in ("0", "3"):
        return "sz"
    if code[:1] in ("4", "8"):
        return "bj"
    return "sh"


def _price_dict(rows):
    return {
        "dates": [r[0] for r in rows],
        "ohlc": [[r[1], r[2], r[3], r[4]] for r in rows],   # open, close, low, high
        "close": [r[2] for r in rows],
    }


def _cn_price(code):
    """Monthly price history. Tries Eastmoney (monthly) first, then Sina daily
    downsampled to month-end — Eastmoney's push2his host is sometimes unreachable."""
    import akshare as ak
    end = datetime.now().strftime("%Y%m%d")
    try:
        h = _retry(lambda: ak.stock_zh_a_hist(symbol=code, period="monthly",
                                              start_date="20210101", end_date=end, adjust="qfq"))
        rows = [(str(r["日期"])[:7], _num(r["开盘"]), _num(r["收盘"]), _num(r["最低"]), _num(r["最高"]))
                for _, r in h.iterrows() if _num(r.get("收盘")) is not None]
        if rows:
            return _price_dict(rows)
    except Exception:
        pass
    # fallback: Sina daily → keep the last trading day of each month
    h = _retry(lambda: ak.stock_zh_a_daily(symbol=_cn_prefix(code) + code,
                                           start_date="20210101", end_date=end, adjust="qfq"))
    monthly = {}
    for _, r in h.iterrows():
        ym = str(r["date"])[:7]
        monthly[ym] = (ym, _num(r["open"]), _num(r["close"]), _num(r["low"]), _num(r["high"]))
    return _price_dict([monthly[k] for k in sorted(monthly)])


# Order matters: "半年度报告" contains "年度报告", so check 中报 before 年报.
_CN_FORM_RULES = [
    ("中报", "半年度报告"), ("年报", "年度报告"), ("一季报", "第一季度"),
    ("三季报", "第三季度"), ("季报", "季度报告"),
]


def _cn_form(title):
    t = title or ""
    for label, kw in _CN_FORM_RULES:
        if kw in t:
            return label
    return "公告"


def _cn_disclosures(code, name="", limit=14):
    """巨潮资讯 (cninfo) official announcements — the A-share primary-source feed."""
    try:
        import akshare as ak
        end = datetime.now()
        start = end - timedelta(days=400)
        df = _retry(lambda: ak.stock_zh_a_disclosure_report_cninfo(
            symbol=code, market="沪深京",
            start_date=start.strftime("%Y%m%d"), end_date=end.strftime("%Y%m%d")))
    except Exception:
        return []
    out = []
    for _, r in df.iterrows():
        title = str(r.get("公告标题") or "").strip()
        if not title:
            continue
        ts = str(r.get("公告时间") or "")[:10] or None
        out.append({"title": title, "form": _cn_form(title),
                    "link": r.get("公告链接"), "time": ts, "type": "filing"})
        if len(out) >= limit:
            break
    return out


def _snapshot_cn(code, market, name=""):
    out = _base_snapshot(code, market)
    warnings = out["warnings"]
    try:
        import akshare as ak
    except ImportError:
        warnings.append("服务器未安装 akshare，无法拉取 A股数据。")
        return out

    # ---- valuation / quote (stock_value_em: latest row + full history for percentile) ----
    try:
        vdf = _retry(lambda: ak.stock_value_em(symbol=code))
        v = vdf.iloc[-1]
        out["quote"] = {
            "price": _num(v.get("当日收盘价")), "change_pct": _num(v.get("当日涨跌幅")),
            "market_cap": _num(v.get("总市值")), "currency": "CNY",
            "fifty_two_week_high": None, "fifty_two_week_low": None,
        }
        pe, pb = _num(v.get("PE(TTM)")), _num(v.get("市净率"))
        out["metrics"].update({"pe": pe, "pb": pb, "ps": _num(v.get("市销率"))})
        dates = [str(d) for d in vdf.get("数据日期", [])]
        out["valuation_history"] = {
            "pe_percentile": _percentile(vdf.get("PE(TTM)", []), pe),
            "pb_percentile": _percentile(vdf.get("市净率", []), pb),
            "span": (f"{dates[0][:7]}~{dates[-1][:7]}" if dates else None),
            "method": "A股历史 PE/PB 分位（精确）",
        }
    except Exception as e:  # noqa: BLE001
        warnings.append(f"估值/行情拉取失败：{str(e)[:120]}")

    # ---- fundamentals (stock_financial_abstract: absolutes + ratios by report date) ----
    try:
        fa = _retry(lambda: ak.stock_financial_abstract(symbol=code))
        rows = {}
        for _, r in fa.iterrows():            # first occurrence of each 指标 wins
            k = r.get("指标")
            if k is not None and k not in rows:
                rows[k] = r
        annual = sorted(c for c in fa.columns if re.fullmatch(r"\d{4}1231", str(c)))[-6:]

        def ser(label):
            r = rows.get(label)
            return [_num(r.get(c)) for c in annual] if r is not None else [None] * len(annual)

        def latest(label):
            r = rows.get(label)
            if r is None:
                return None
            for c in reversed(annual):        # most recent annual with a value
                val = _num(r.get(c))
                if val is not None:
                    return val
            return None

        revenue = ser("营业总收入")
        out["financials"] = {
            "years": [str(c)[:4] for c in annual],
            "revenue": revenue,
            "net_income": ser("归母净利润"),
            "gross_profit": None,
            "operating_income": None,
            "eps": ser("基本每股收益"),
            "fcf": ser("经营现金流量净额"),       # OCF as a cash-quality proxy for the radar
            "gross_margin": ser("毛利率"),
            "operating_margin": None,
            "net_margin": ser("销售净利率"),
        }
        # debt/assets → debt/equity (%) so the radar's D/E bands apply uniformly
        d2a = latest("资产负债率")
        d2e = round(d2a / (100 - d2a) * 100, 1) if (d2a is not None and d2a < 100) else None
        out["metrics"].update({
            "roe": latest("净资产收益率(ROE)"),
            "gross_margin": latest("毛利率"),
            "net_margin": latest("销售净利率"),
            "revenue_growth": latest("营业总收入增长率"),
            "earnings_growth": latest("归属母公司净利润增长率"),
            "current_ratio": latest("流动比率"),
            "debt_to_equity": d2e,
            "debt_to_assets": d2a,
        })
        # forensics (A股 partial: 利润含金量 via OCF + 商誉占净资产; 应收/EBIT not in abstract)
        try:
            out["quality_signals"] = _fx.signals(
                net_income=ser("归母净利润"), revenue=revenue, fcf=ser("经营现金流量净额"),
                goodwill_latest=latest("商誉"), equity_latest=latest("股东权益合计(净资产)"),
            )
        except Exception:  # noqa: BLE001
            pass
    except Exception as e:  # noqa: BLE001
        warnings.append(f"财务数据拉取失败：{str(e)[:120]}")

    # ---- price history (monthly, qfq-adjusted; Eastmoney→Sina fallback) ----
    try:
        out["price_history"] = _cn_price(code)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"价格历史拉取失败：{str(e)[:120]}")

    out["profile"]["name"] = name or out["profile"].get("name") or code
    try:
        out["radar"] = _radar(out["metrics"], out.get("financials") or {})
    except Exception as e:  # noqa: BLE001
        warnings.append(f"健康评分计算失败：{str(e)[:120]}")
    # valuation-consensus signals — A股 uses 经营现金流 as the owner-earnings proxy;
    # EV/EBIT stays "待同行" (akshare net-debt/EBIT not wired yet).
    try:
        fin = out.get("financials") or {}
        out["valuation_signals"] = _val.signals(
            market_cap=out["quote"].get("market_cap"),
            owner_earnings=(fin.get("fcf") or [None])[-1],
            net_debt=None,
            ebit=None,
            pe_percentile=(out.get("valuation_history") or {}).get("pe_percentile"),
            ten_year_yield=ten_year_yield(market),
            hist_rev_cagr=_val._cagr(fin.get("revenue")),
            hist_eps_cagr=_val._cagr(fin.get("eps")),
        )
    except Exception as e:  # noqa: BLE001
        warnings.append(f"估值信号计算失败：{str(e)[:120]}")
    try:
        out["history_position"] = _fx.history_position(out.get("financials") or {})
    except Exception:  # noqa: BLE001
        pass
    try:
        m = out.get("metrics") or {}
        out["macro_signal"] = _macro.assemble(
            macro_env(market), d2e=m.get("debt_to_equity"), pe=m.get("pe"),
            growth=m.get("revenue_growth"), market=market)
    except Exception:  # noqa: BLE001
        pass
    return out


def _news_cn(code, name=""):
    out = {"ticker": code, "market": "A股", "news": [], "filings": [], "warnings": []}
    try:
        import akshare as ak
        df = _retry(lambda: ak.stock_news_em(symbol=code))
        for _, r in df.iterrows():
            title = str(r.get("新闻标题") or "").strip()
            if not title:
                continue
            ts = str(r.get("发布时间") or "")
            out["news"].append({"title": title, "link": r.get("新闻链接"),
                                "publisher": str(r.get("文章来源") or ""), "time": ts, "type": "news"})
            if len(out["news"]) >= 15:
                break
    except ImportError:
        out["warnings"].append("服务器未安装 akshare。")
    except Exception as e:  # noqa: BLE001
        out["warnings"].append(f"新闻拉取失败：{str(e)[:120]}")
    try:
        out["filings"] = _cn_disclosures(code, name)
    except Exception as e:  # noqa: BLE001
        out["warnings"].append(f"巨潮公告拉取失败：{str(e)[:120]}")
    return out


# --------------------------------------------------------------------------- #
# public API
# --------------------------------------------------------------------------- #

# Bump when the snapshot shape gains fields, so the frontend auto-refreshes stale
# cached snapshots once instead of showing empty new panels until a manual 刷新.
SNAPSHOT_SCHEMA = 2


def _base_snapshot(ticker, market):
    return {
        "ticker": ticker, "market": market,
        "as_of": datetime.now(timezone.utc).isoformat(),
        "_schema": SNAPSHOT_SCHEMA,
        "profile": {"name": ticker}, "quote": {}, "metrics": {},
        "financials": {}, "price_history": {}, "radar": {},
        "valuation_history": {}, "valuation_signals": {}, "quality_signals": {},
        "history_position": {}, "macro_signal": {}, "warnings": [],
    }


def snapshot(ticker: str, market: str = "美股", name: str = "") -> dict:
    """Full company snapshot: profile, quote, metrics, financials, price, radar.

    Same dict shape for every market; only the data source differs (yfinance for
    US, akshare for A-share). Other markets return a graceful stub.
    """
    raw = (ticker or "").strip()
    if _is_cn(market):
        return _snapshot_cn(_cn_code(raw), market, name=name)
    if not _is_us(market):
        out = _base_snapshot(raw, market)
        out["warnings"].append("港股 / 加密数据源尚未接入。当前支持美股 + A股。")
        return out
    return _snapshot_us(raw.upper(), market)


def _snapshot_us(ticker: str, market: str = "美股") -> dict:
    warnings = []
    out = _base_snapshot(ticker, market)
    out["warnings"] = warnings
    try:
        import yfinance as yf
    except ImportError:
        warnings.append("服务器未安装 yfinance，无法拉取实时数据。")
        return out

    t = yf.Ticker(ticker)
    try:
        info = t.info or {}
    except Exception as e:  # noqa: BLE001
        info = {}
        warnings.append(f"行情/资料拉取失败：{str(e)[:120]}")

    out["profile"] = {
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "exchange": info.get("fullExchangeName") or info.get("exchange"),
        "currency": info.get("currency"),
        "country": info.get("country"),
        "employees": info.get("fullTimeEmployees"),
        "website": info.get("website"),
        "summary": info.get("longBusinessSummary"),
    }
    out["quote"] = {
        "price": _num(info.get("currentPrice") or info.get("regularMarketPrice")),
        "change_pct": _num(info.get("regularMarketChangePercent")),
        "market_cap": _num(info.get("marketCap")),
        "currency": info.get("currency"),
        "fifty_two_week_high": _num(info.get("fiftyTwoWeekHigh")),
        "fifty_two_week_low": _num(info.get("fiftyTwoWeekLow")),
    }
    out["metrics"] = {
        "pe": _num(info.get("trailingPE")),
        "forward_pe": _num(info.get("forwardPE")),
        "pb": _num(info.get("priceToBook")),
        "ps": _num(info.get("priceToSalesTrailing12Months")),
        # yfinance >=1.x already returns dividendYield as a percentage (e.g. 0.37 = 0.37%).
        "dividend_yield": _num(info.get("dividendYield")),
        "roe": _pct(info.get("returnOnEquity")),
        "gross_margin": _pct(info.get("grossMargins")),
        "operating_margin": _pct(info.get("operatingMargins")),
        "net_margin": _pct(info.get("profitMargins")),
        "debt_to_equity": _num(info.get("debtToEquity")),
        "current_ratio": _num(info.get("currentRatio")),
        "revenue_growth": _pct(info.get("revenueGrowth")),
        "earnings_growth": _pct(info.get("earningsGrowth")),
        "fcf": _num(info.get("freeCashflow")),
    }
    try:
        out["financials"] = _financials(t)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"财务报表解析失败：{str(e)[:120]}")
    try:
        out["price_history"] = _price_history(t)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"价格历史拉取失败：{str(e)[:120]}")
    try:
        out["radar"] = _radar(out["metrics"], out.get("financials") or {})
    except Exception as e:  # noqa: BLE001
        warnings.append(f"健康评分计算失败：{str(e)[:120]}")
    # historical valuation position — compute a precise P/E·P/B percentile from our
    # own yfinance data; fall back to a price percentile only if EPS history is too thin.
    try:
        vh = _us_valuation_history(t, info, out.get("price_history") or {}, out.get("financials") or {})
        if not vh:
            closes = (out.get("price_history") or {}).get("close") or []
            vh = {
                "price_percentile": _percentile(closes, out["quote"].get("price")),
                "span": "近5年（月）",
                "method": "美股近似：当前价在近5年价格分位（历史EPS不足，无法算P/E分位）",
            }
        out["valuation_history"] = vh
    except Exception:  # noqa: BLE001
        pass
    # valuation-consensus signals (reverse DCF + four tools)
    try:
        fin = out.get("financials") or {}
        oi = fin.get("operating_income") or []
        net_debt = (_num(info.get("totalDebt")) or 0) - (_num(info.get("totalCash")) or 0)
        out["valuation_signals"] = _val.signals(
            market_cap=out["quote"].get("market_cap"),
            owner_earnings=_num(info.get("freeCashflow")) or (fin.get("fcf") or [None])[-1],
            net_debt=net_debt,
            ebit=oi[-1] if oi else None,
            pe_percentile=(out.get("valuation_history") or {}).get("pe_percentile"),
            ten_year_yield=ten_year_yield(market),
            hist_rev_cagr=_val._cagr(fin.get("revenue")),
            hist_eps_cagr=_val._cagr(fin.get("eps")),
        )
    except Exception as e:  # noqa: BLE001
        warnings.append(f"估值信号计算失败：{str(e)[:120]}")
    # earnings-quality / capital-transmission forensics (资金传导支柱)
    try:
        fin = out.get("financials") or {}
        fy = fin.get("years") or []
        bs = getattr(t, "balance_sheet", None)
        bal_years = [str(c.year) for c in bs.columns[::-1]] if (bs is not None and not getattr(bs, "empty", True)) else []

        def _bseries(*names):
            r = _row(bs, *names)
            return dict(zip(bal_years, r)) if r else {}

        recv = _bseries("Accounts Receivable", "Receivables", "Net Receivables")
        invn = _bseries("Inventory")
        gw = _bseries("Goodwill", "Goodwill And Other Intangible Assets")
        eq = _bseries("Stockholders Equity", "Common Stock Equity", "Total Stockholder Equity")
        debt = _bseries("Total Debt", "Total Debt And Capital Lease Obligation")
        cash = _bseries("Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments")
        invcap = [((debt.get(y) or 0) + eq[y] - (cash.get(y) or 0)) if eq.get(y) is not None else None for y in fy]

        def _last(d):
            return next((d[y] for y in reversed(fy) if d.get(y) is not None), None)

        ie_row = _row(getattr(t, "income_stmt", None), "Interest Expense", "Interest Expense Non Operating")
        dv_row = _row(getattr(t, "cashflow", None), "Cash Dividends Paid", "Common Stock Dividend Paid", "Cash Dividend Paid")
        out["quality_signals"] = _fx.signals(
            net_income=fin.get("net_income"), revenue=fin.get("revenue"),
            fcf=fin.get("fcf"), ebit=fin.get("operating_income"),
            receivables=[recv.get(y) for y in fy], inventory=[invn.get(y) for y in fy],
            goodwill_latest=_last(gw), equity_latest=_last(eq),
            invested_capital=invcap, payout_ratio=_num(info.get("payoutRatio")),
            interest_expense=(ie_row[-1] if ie_row else None),
            dividends_paid=(dv_row[-1] if dv_row else None),
        )
    except Exception as e:  # noqa: BLE001
        warnings.append(f"盈余质量取证失败：{str(e)[:120]}")
    try:
        out["history_position"] = _fx.history_position(out.get("financials") or {})
    except Exception:  # noqa: BLE001
        pass
    # macro capital transmission (资金传导支柱·宏观层)
    try:
        m = out.get("metrics") or {}
        oi = (out.get("financials") or {}).get("operating_income") or []
        ebit = oi[-1] if oi else None
        ie = _row(getattr(t, "income_stmt", None), "Interest Expense", "Interest Expense Non Operating")
        ie_latest = abs(ie[-1]) if (ie and ie[-1]) else None
        cov = round(ebit / ie_latest, 1) if (ebit and ie_latest and ie_latest > 0) else None
        out["macro_signal"] = _macro.assemble(
            macro_env(market), d2e=m.get("debt_to_equity"), interest_coverage=cov,
            pe=m.get("pe"), growth=m.get("revenue_growth"), market=market)
    except Exception as e:  # noqa: BLE001
        warnings.append(f"宏观传导计算失败：{str(e)[:120]}")
    out["_t_cached"] = False
    return out


def news(ticker: str, market: str = "美股", name: str = "") -> dict:
    """Company 消息流: news headlines + primary-source filings (SEC for US, cninfo for A-share)."""
    raw = (ticker or "").strip()
    if _is_cn(market):
        return _news_cn(_cn_code(raw), name)
    ticker = raw.upper()
    out = {"ticker": ticker, "market": market, "news": [], "filings": [], "warnings": []}
    if not _is_us(market):
        out["warnings"].append("港股 / 加密消息流尚未接入。当前支持美股 + A股。")
        return out
    try:
        import yfinance as yf
        t = yf.Ticker(ticker)
        out["news"] = _yf_news(t, name, ticker)
    except ImportError:
        out["warnings"].append("服务器未安装 yfinance。")
        out["news"] = _google_news(name or ticker)
    except Exception as e:  # noqa: BLE001
        out["warnings"].append(f"新闻拉取失败：{str(e)[:120]}")
        out["news"] = _google_news(name or ticker)
    try:
        out["filings"] = sec_filings(ticker)
    except Exception as e:  # noqa: BLE001
        out["warnings"].append(f"SEC 文件拉取失败：{str(e)[:120]}")
    return out
