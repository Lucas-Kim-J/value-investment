#!/usr/bin/env python3
"""Daily briefing bot for the value-investing routine — delivered to Feishu via hermes.

Builds a concise pre-market briefing from free data sources and delivers it to
Feishu using the server's `hermes send` (no bot tokens in this code — hermes
owns the Feishu credentials). Designed to run ON THE SERVER where hermes lives,
scheduled by `hermes cron` or system cron.

Usage:
    python briefing.py                 # build + send to Feishu (default target)
    python briefing.py --dry-run       # build + print to stdout, do not send
    python briefing.py --to feishu     # explicit target (see `hermes send --list`)
    python briefing.py --llm           # use Claude to summarize (needs ANTHROPIC_API_KEY)

Delivery contract:
    The briefing text is piped to `hermes send --to <target> --subject <subject>`.
    Run `hermes send --list` on the server to see configured targets.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml
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
    if yf is None:
        return None
    try:
        h = yf.Ticker(symbol).history(period="5d")
        if len(h) < 2:
            return None
        close = float(h["Close"].iloc[-1])
        prev = float(h["Close"].iloc[-2])
        return {"close": close, "change_pct": (close - prev) / prev * 100}
    except Exception as e:
        return {"error": str(e)}


def fetch_us_macro() -> dict[str, Any]:
    symbols = {
        "S&P500": "^GSPC", "Nasdaq": "^IXIC", "VIX": "^VIX",
        "DXY": "DX-Y.NYB", "10Y": "^TNX", "BTC": "BTC-USD", "ETH": "ETH-USD",
    }
    out = {}
    for label, sym in symbols.items():
        q = fetch_us_quote(sym)
        if q:
            out[label] = q
    return out


def fetch_us_portfolio(tickers: list[str]) -> dict[str, Any]:
    out = {}
    for t in tickers:
        q = fetch_us_quote(t)
        if q:
            out[t] = q
    return out


def fetch_a_share_portfolio(tickers: list[str]) -> dict[str, Any]:
    """tickers 形如 ['sh600519', 'sz000858']."""
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
            out[t] = {"close": close, "change_pct": (close - prev) / prev * 100}
        except Exception as e:
            out[t] = {"error": str(e)}
    return out


def fetch_northbound_flow() -> str | None:
    if ak is None:
        return None
    try:
        df = ak.stock_hsgt_fund_flow_summary_em()
        if df is None or df.empty:
            return None
        return df.tail(3).to_string(index=False)
    except Exception as e:
        return f"[northbound fetch failed: {e}]"


def fetch_earnings_calendar(tickers: list[str], days_ahead: int = 7) -> list[dict]:
    if yf is None:
        return []
    out = []
    now = datetime.now(timezone.utc)
    cutoff = now + timedelta(days=days_ahead)
    for t in tickers:
        try:
            cal = yf.Ticker(t).calendar
            if cal is None or not hasattr(cal, "to_dict"):
                continue
            d = cal.to_dict()
            dates = d.get("Earnings Date")
            if isinstance(dates, list) and dates:
                ed = dates[0]
                if isinstance(ed, datetime) and now.date() <= ed.date() <= cutoff.date():
                    out.append({"ticker": t, "date": ed.strftime("%Y-%m-%d")})
        except Exception:
            continue
    return out


# ---------- Briefing text (plain text, Feishu-friendly) ----------

def build_text(data: dict, today: str) -> str:
    lines = [f"📊 每日早报 · {today}", ""]

    macro = data.get("macro", {})
    if macro:
        lines.append("【市场快讯】")
        for label, q in macro.items():
            if isinstance(q, dict) and "close" in q:
                lines.append(f"  {label}: {q['close']:.2f} ({q['change_pct']:+.2f}%)")
        lines.append("")

    portfolio = data.get("us_portfolio", {})
    if portfolio:
        lines.append("【美股持仓 / watchlist】")
        for t, q in portfolio.items():
            if isinstance(q, dict) and "close" in q:
                flag = " ⚠️" if abs(q["change_pct"]) >= 2 else ""
                lines.append(f"  {t}: ${q['close']:.2f} ({q['change_pct']:+.2f}%){flag}")
        lines.append("")

    a_share = data.get("a_share_portfolio", {})
    if a_share:
        lines.append("【A股持仓】")
        for t, q in a_share.items():
            if isinstance(q, dict) and "close" in q:
                flag = " ⚠️" if abs(q["change_pct"]) >= 2 else ""
                lines.append(f"  {t}: ¥{q['close']:.2f} ({q['change_pct']:+.2f}%){flag}")
        lines.append("")

    nb = data.get("northbound")
    if nb:
        lines.append("【北向资金】")
        lines.append("  " + str(nb).replace("\n", "\n  "))
        lines.append("")

    earnings = data.get("earnings", [])
    if earnings:
        lines.append("【本周财报 (7d)】")
        for e in earnings:
            lines.append(f"  {e['ticker']}: {e['date']}")
        lines.append("")

    lines.append("【今日校验点】")
    lines.append("  · 持仓 thesis 有无被昨夜信息证伪？")
    lines.append("  · |涨跌|>2% 的标的，是噪音还是 thesis 变化？")
    lines.append("")
    lines.append("— 本早报仅为信息汇总，不构成投资建议。决策请回到 decision log。")
    return "\n".join(lines)


def summarize_with_claude(data: dict, today: str, methodology_ref: str = "") -> str | None:
    """Optional LLM summary. Returns None if unavailable (caller falls back)."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        from anthropic import Anthropic
    except ImportError:
        return None

    client = Anthropic(api_key=api_key)
    prompt = f"""你是一位价值投资学习者（B 轨，10h/周）的每日早报助手。基于今日数据生成简洁中文晨报，≤ 500 字，纯文本（无 markdown 星号），适合飞书阅读。

强制要求：不预测股价；不写"建议买入/卖出/加油"；引用具体数字；简洁不夸张。

结构：市场快讯（美股隔夜 + 加密 + VIX/DXY/10Y）→ 持仓异动（|涨跌|>2% 重点）→ A股盘前（北向 + 持仓）→ 本周财报 → 今日校验点（一句话）。

今日数据：
日期：{today}
美股宏观：{json.dumps(data.get("macro", {}), ensure_ascii=False)}
美股持仓/watchlist：{json.dumps(data.get("us_portfolio", {}), ensure_ascii=False)}
A股持仓：{json.dumps(data.get("a_share_portfolio", {}), ensure_ascii=False)}
北向资金：{data.get("northbound") or "数据不可用"}
本周财报：{json.dumps(data.get("earnings", []), ensure_ascii=False)}

{methodology_ref}

直接输出晨报正文，不要前缀解释。"""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=900,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text
    except Exception as e:
        print(f"[claude summary failed: {e}; using plain text]", file=sys.stderr)
        return None


# ---------- Delivery via hermes ----------

def send_via_hermes(text: str, target: str, subject: str | None = None) -> bool:
    """Pipe the briefing to `hermes send`. Requires hermes on PATH (run on server)."""
    cmd = ["hermes", "send", "--to", target]
    if subject:
        cmd += ["--subject", subject]
    try:
        r = subprocess.run(cmd, input=text, text=True, capture_output=True, timeout=60)
        if r.returncode == 0:
            print(r.stdout.strip() or f"sent to {target}")
            return True
        print(f"hermes send failed (exit {r.returncode}): {r.stderr.strip()}", file=sys.stderr)
        return False
    except FileNotFoundError:
        print(
            "未找到 hermes。请在装有 hermes 的服务器上运行本脚本；"
            "本地预览请用 --dry-run。",
            file=sys.stderr,
        )
        return False
    except subprocess.TimeoutExpired:
        print("hermes send timed out", file=sys.stderr)
        return False


# ---------- Main ----------

def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"config.yaml not found at {CONFIG_PATH}. Copy config.example.yaml.", file=sys.stderr)
        sys.exit(1)
    with CONFIG_PATH.open() as f:
        return yaml.safe_load(f) or {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Daily briefing bot → Feishu via hermes")
    parser.add_argument("--dry-run", action="store_true", help="Print briefing, do not send")
    parser.add_argument("--to", dest="target", default=None, help="hermes send target (default: config feishu_target or 'feishu')")
    parser.add_argument("--llm", action="store_true", help="Use Claude to summarize (needs ANTHROPIC_API_KEY)")
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

    briefing = None
    if args.llm:
        briefing = summarize_with_claude(data, today, config.get("methodology_context", ""))
    if not briefing:
        briefing = build_text(data, today)

    if args.dry_run:
        print(briefing)
        return 0

    target = args.target or config.get("feishu_target", "feishu")
    ok = send_via_hermes(briefing, target, subject=f"📊 每日早报 · {today}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
