#!/usr/bin/env python3
"""Daily briefing TG bot for value investing routine.

Usage:
    python briefing.py              # run once, push to Telegram
    python briefing.py --dry-run    # build briefing, print to stdout, don't push

Env vars (load from .env):
    ANTHROPIC_API_KEY
    TELEGRAM_BOT_TOKEN
    TELEGRAM_CHAT_ID

Config: config.yaml (copy from config.example.yaml).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml
from anthropic import Anthropic
from dotenv import load_dotenv

# Optional data libs — fail soft if missing
try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import akshare as ak
except ImportError:
    ak = None


CONFIG_PATH = Path(__file__).parent / "config.yaml"
load_dotenv(Path(__file__).parent / ".env")


# ---------- Data fetchers ----------

def fetch_us_quote(symbol: str) -> dict[str, float] | None:
    """Single symbol US/global quote via yfinance."""
    if yf is None:
        return None
    try:
        t = yf.Ticker(symbol)
        h = t.history(period="5d")
        if len(h) < 2:
            return None
        close = float(h["Close"].iloc[-1])
        prev = float(h["Close"].iloc[-2])
        return {
            "close": close,
            "change_pct": (close - prev) / prev * 100,
        }
    except Exception as e:
        return {"error": str(e)}


def fetch_us_macro() -> dict[str, Any]:
    """Overnight macro snapshot."""
    symbols = {
        "S&P500": "^GSPC",
        "Nasdaq": "^IXIC",
        "VIX": "^VIX",
        "DXY": "DX-Y.NYB",
        "10Y": "^TNX",
        "BTC": "BTC-USD",
        "ETH": "ETH-USD",
    }
    out = {}
    for label, sym in symbols.items():
        q = fetch_us_quote(sym)
        if q:
            out[label] = q
    return out


def fetch_us_portfolio(tickers: list[str]) -> dict[str, Any]:
    """Holdings + watchlist daily quotes."""
    out = {}
    for t in tickers:
        q = fetch_us_quote(t)
        if q:
            out[t] = q
    return out


def fetch_a_share_portfolio(tickers: list[str]) -> dict[str, Any]:
    """A股持仓行情。tickers 形如 ['sh600519', 'sz000858']."""
    if ak is None or not tickers:
        return {}
    out = {}
    for t in tickers:
        try:
            df = ak.stock_zh_a_daily(symbol=t, adjust="qfq")
            if df is None or len(df) < 2:
                continue
            close = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2])
            out[t] = {
                "close": close,
                "change_pct": (close - prev) / prev * 100,
            }
        except Exception as e:
            out[t] = {"error": str(e)}
    return out


def fetch_northbound_flow() -> str | None:
    """北向资金净流入概况（最近一日）。返回简短字符串或 None。"""
    if ak is None:
        return None
    try:
        # 函数名版本之间会变；常见的有 stock_hsgt_fund_flow_summary_em
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is None or df.empty:
            return None
        # 返回最近一行的关键字段（具体列名以 akshare 当前为准）
        return df.tail(3).to_string(index=False)
    except Exception as e:
        return f"[northbound fetch failed: {e}]"


def fetch_earnings_calendar(tickers: list[str], days_ahead: int = 7) -> list[dict]:
    """未来 N 天 watchlist 财报日历."""
    if yf is None:
        return []
    out = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)
    for t in tickers:
        try:
            ticker = yf.Ticker(t)
            cal = ticker.calendar
            if cal is None:
                continue
            # yfinance calendar API has changed multiple times; handle both shapes
            if hasattr(cal, "to_dict"):
                d = cal.to_dict()
                # newer API returns dict keyed by field name
                if "Earnings Date" in d:
                    dates = d["Earnings Date"]
                    if isinstance(dates, list) and dates:
                        ed = dates[0]
                        if isinstance(ed, datetime) and now.date() <= ed.date() <= cutoff.date():
                            out.append({"ticker": t, "date": ed.strftime("%Y-%m-%d")})
        except Exception:
            continue
    return out


# ---------- Claude summarization ----------

def summarize_with_claude(data: dict, today: str, methodology_ref: str = "") -> str:
    """Generate Chinese briefing using Claude."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_summary(data, today)

    client = Anthropic(api_key=api_key)

    prompt = f"""你是一位价值投资学习者（B 轨，10h/周）的每日早报助手。基于今日数据生成简洁中文晨报，≤ 600 字。

**强制要求**：
- 不预测股价
- 不写"加油 / 建议买入 / 应该卖出"类内容
- 引用具体数字
- 简洁、不夸张
- Telegram Markdown 格式（用 *bold* 和 _italic_）

**结构**：
1. *市场快讯* — 美股隔夜 + 加密 + 关键宏观（VIX、DXY、10Y）
2. *持仓异动* — 重点关注 |涨跌| > 2%
3. *A 股盘前* — 北向资金 + 持仓预期
4. *本周财报日历* — watchlist 内
5. *今日校验点* — 一句话："今天需要警惕什么 / 今日 thesis 校验点是什么"

**今日数据**：
- 日期：{today}
- 美股宏观：{json.dumps(data.get("macro", {}), ensure_ascii=False)}
- 美股持仓 + watchlist：{json.dumps(data.get("us_portfolio", {}), ensure_ascii=False)}
- A 股持仓：{json.dumps(data.get("a_share_portfolio", {}), ensure_ascii=False)}
- 北向资金：{data.get("northbound") or "数据不可用"}
- 本周财报：{json.dumps(data.get("earnings", []), ensure_ascii=False)}

{methodology_ref}

请直接输出 Markdown 格式的晨报内容，不要任何前缀解释。"""

    try:
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        return _fallback_summary(data, today, error=str(e))


def _fallback_summary(data: dict, today: str, error: str = "") -> str:
    """No-LLM fallback: just dump key numbers."""
    lines = [f"📊 *Daily Briefing — {today}*", ""]
    if error:
        lines.append(f"_LLM unavailable: {error}_")
        lines.append("")

    macro = data.get("macro", {})
    if macro:
        lines.append("*Macro:*")
        for label, q in macro.items():
            if isinstance(q, dict) and "close" in q:
                lines.append(f"  • {label}: {q['close']:.2f} ({q['change_pct']:+.2f}%)")
        lines.append("")

    portfolio = data.get("us_portfolio", {})
    if portfolio:
        lines.append("*US Portfolio:*")
        for t, q in portfolio.items():
            if isinstance(q, dict) and "close" in q:
                lines.append(f"  • {t}: ${q['close']:.2f} ({q['change_pct']:+.2f}%)")
        lines.append("")

    a_share = data.get("a_share_portfolio", {})
    if a_share:
        lines.append("*A股 Portfolio:*")
        for t, q in a_share.items():
            if isinstance(q, dict) and "close" in q:
                lines.append(f"  • {t}: ¥{q['close']:.2f} ({q['change_pct']:+.2f}%)")
        lines.append("")

    earnings = data.get("earnings", [])
    if earnings:
        lines.append("*Upcoming Earnings (7d):*")
        for e in earnings:
            lines.append(f"  • {e['ticker']}: {e['date']}")

    return "\n".join(lines)


# ---------- Telegram push ----------

def push_telegram(text: str) -> bool:
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not bot_token or not chat_id:
        print("[Telegram creds missing; printing instead]\n")
        print(text)
        return False

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    # Truncate to 4000 to leave room for Markdown safety
    text = text[:4000]
    try:
        r = requests.post(
            url,
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
            timeout=30,
        )
        if r.ok:
            return True
        # Markdown parse can fail with unbalanced markers; retry as plain text
        print(f"Markdown push failed ({r.status_code}); retrying as plain text", file=sys.stderr)
        r = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=30)
        return r.ok
    except Exception as e:
        print(f"Telegram push exception: {e}", file=sys.stderr)
        return False


# ---------- Main ----------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"config.yaml not found at {CONFIG_PATH}. Copy config.example.yaml.", file=sys.stderr)
        sys.exit(1)
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily briefing TG bot")
    parser.add_argument("--dry-run", action="store_true", help="Print briefing, don't push to Telegram")
    args = parser.parse_args(argv)

    config = load_config()
    today = datetime.now().strftime("%Y-%m-%d %A")

    us_tickers = config.get("us_holdings", []) + config.get("us_watchlist", [])
    a_share_tickers = config.get("a_share_holdings", [])
    earnings_tickers = config.get("us_watchlist", []) + config.get("us_holdings", [])

    data = {
        "macro": fetch_us_macro(),
        "us_portfolio": fetch_us_portfolio(us_tickers),
        "a_share_portfolio": fetch_a_share_portfolio(a_share_tickers),
        "northbound": fetch_northbound_flow(),
        "earnings": fetch_earnings_calendar(earnings_tickers),
    }

    methodology_ref = config.get("methodology_context", "")
    briefing = summarize_with_claude(data, today, methodology_ref)

    if args.dry_run:
        print(briefing)
        return 0

    ok = push_telegram(briefing)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
