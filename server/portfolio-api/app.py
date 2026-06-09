#!/usr/bin/env python3
"""Portfolio input API for the value-investing system (PostgreSQL-backed).

A tiny Flask service behind nginx (proxied at /api/). Provides:
  - access-code login (whitelist) → signed session cookie
  - per-user holdings storage in PostgreSQL (durable, transactional)
  - on-demand 规范报告 generation via the server's `hermes` agent (async)
  - optional push of the report to Feishu (for whitelisted users)

Secrets live ONLY on the server (never in the repo):
  - VI_CODES_FILE     JSON mapping {access_code: username}
  - VI_SECRET_KEY     Flask session signing key
  - VI_DATABASE_URL   postgresql://vi_app:...@127.0.0.1:5432/value_investment
"""
from __future__ import annotations

import datetime
import json
import os
import subprocess
import threading
import time
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from flask import Flask, jsonify, request, session

CODES_FILE = Path(os.environ.get("VI_CODES_FILE", "/etc/value-investment/access-codes.json"))
DB_URL = os.environ.get("VI_DATABASE_URL", "")

app = Flask(__name__)
app.secret_key = os.environ.get("VI_SECRET_KEY", "dev-insecure-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),
)

# Users whose generated report may be pushed to *their own* Feishu.
FEISHU_USERS = {"lucas": "feishu"}

# "hermes" (prod) calls the real LLM; "mock" (local dev) returns a placeholder.
REPORT_MODE = os.environ.get("VI_REPORT_MODE", "hermes")
_MOCK_REPORT = (
    "## 组合总览\n\n（本地 mock 模式）这是本地开发的占位报告——未调用 hermes。\n\n"
    "- prompt 长度：{n} 字符\n- 生产环境由服务器上的 hermes 按方法论生成真实报告\n\n"
    "## 下一步\n\n在服务器上 `VI_REPORT_MODE` 为默认 hermes，会生成真实的逐仓位审视报告。\n"
)

METHODOLOGY_CONTEXT = """【方法论核心 v1.1】
- B 轨学习者(~10h/周)，起点流派 Pabrai + Marks（先精通这两派 3 年再吸收其他）。
- 配置重心：美股~50% / A股~30% / 加密≤5%净资产（加密是非对称配置，不是价值投资）。
- 估值前 180 天禁用 DCF，用四工具三角验证：① 反向 DCF（当前价隐含的增长率是否合理）② 历史 P/E 百分位（0-25% 才算历史便宜区）③ EV/EBIT 同行对比（最便宜 30% 且 ROIC 不输平均）④ Owner Earnings Yield vs 10Y（差额>+4% 才算合理 hurdle）。至少 2 个独立角度一致便宜才进深度研究。
- 每笔决策必过 Pabrai 三问：① 最坏亏多少（具体金额）② 能否在心理+财务上承受 ③ 赔率≥2:1。任一 no → 不下注。
- 每笔持仓必须有：可证伪的 thesis（哪个具体事件发生就证明它错了）+ 明确退出条件。
- 价值陷阱红旗：低 P/E 但行业结构性衰退 / 高股息靠借债(payout>100%) / 周期顶部低 P/E / 经营现金流长期<净利润 / 应收增速>营收增速 / 商誉>净资产 30%。
- 卖出三条件：thesis 被证伪 / 严重高估(>内在价值 50%) / 出现明显更好的机会。
- 心理纪律：损失厌恶、锚定、处置效应、FOMO；决策前记录情绪状态。"""


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _codes() -> dict:
    try:
        return json.loads(CODES_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _current_user() -> str | None:
    return session.get("user")


# ---------- database ----------

@contextmanager
def _db():
    conn = psycopg2.connect(DB_URL)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _init_db() -> None:
    if not DB_URL:
        return
    with _db() as c, c.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS holdings (
                id           SERIAL PRIMARY KEY,
                username     TEXT NOT NULL,
                market       TEXT,
                ticker       TEXT,
                name         TEXT,
                buy_date     TEXT,
                cost         DOUBLE PRECISION,
                position_pct DOUBLE PRECISION,
                note         TEXT,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_holdings_user ON holdings(username);
            CREATE TABLE IF NOT EXISTS reports (
                username     TEXT PRIMARY KEY,
                status       TEXT,
                report       TEXT,
                error        TEXT,
                started_at   DOUBLE PRECISION,
                generated_at TIMESTAMPTZ,
                updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            """
        )


def _load(user: str) -> dict:
    with _db() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT market, ticker, name, buy_date, cost, position_pct, note "
            "FROM holdings WHERE username=%s ORDER BY id",
            (user,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT max(updated_at) AS u FROM holdings WHERE username=%s", (user,))
        u = cur.fetchone()["u"]
    return {"holdings": rows, "updated_at": u.isoformat() if u else None}


def _save(user: str, holdings: list[dict]) -> None:
    # transactional replace: delete-then-insert in one transaction (atomic)
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM holdings WHERE username=%s", (user,))
        for h in holdings:
            cur.execute(
                "INSERT INTO holdings(username, market, ticker, name, buy_date, cost, position_pct, note) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (user, h["market"], h["ticker"], h["name"], h["buy_date"], h["cost"], h["position_pct"], h["note"]),
            )


def _read_report_state(user: str) -> dict | None:
    with _db() as c, c.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
        cur.execute(
            "SELECT status, report, error, started_at, generated_at FROM reports WHERE username=%s",
            (user,),
        )
        r = cur.fetchone()
    if not r:
        return None
    d = dict(r)
    if d.get("generated_at"):
        d["generated_at"] = d["generated_at"].isoformat()
    return d


def _write_report_state(user: str, state: dict) -> None:
    with _db() as c, c.cursor() as cur:
        cur.execute(
            """
            INSERT INTO reports(username, status, report, error, started_at, generated_at, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (username) DO UPDATE SET
                status=EXCLUDED.status, report=EXCLUDED.report, error=EXCLUDED.error,
                started_at=EXCLUDED.started_at, generated_at=EXCLUDED.generated_at, updated_at=now()
            """,
            (user, state.get("status"), state.get("report"), state.get("error"),
             state.get("started_at"), state.get("generated_at")),
        )


try:
    _init_db()
except Exception as _e:  # noqa: BLE001
    print(f"[warn] _init_db failed: {_e}")


# ---------- auth ----------

@app.get("/api/health")
def health():
    db_ok = False
    try:
        with _db() as c, c.cursor() as cur:
            cur.execute("SELECT 1")
            db_ok = cur.fetchone()[0] == 1
    except Exception:
        db_ok = False
    return {"ok": True, "db": db_ok, "time": _now()}


@app.post("/api/login")
def login():
    body = request.get_json(force=True, silent=True) or {}
    code = str(body.get("code", "")).strip()
    user = _codes().get(code)
    if not user:
        return {"error": "访问码无效"}, 401
    session.permanent = True
    session["user"] = user
    return {"ok": True, "user": user}


@app.post("/api/logout")
def logout():
    session.clear()
    return {"ok": True}


@app.get("/api/me")
def me():
    return {"user": _current_user()}


# ---------- holdings ----------

@app.get("/api/holdings")
def get_holdings():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    return jsonify(_load(user))


@app.put("/api/holdings")
def put_holdings():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    holdings = body.get("holdings")
    if not isinstance(holdings, list):
        return {"error": "holdings must be a list"}, 400

    clean = []
    for h in holdings[:200]:
        if not isinstance(h, dict):
            continue
        clean.append(
            {
                "market": str(h.get("market", ""))[:16],
                "ticker": str(h.get("ticker", "")).strip()[:32],
                "name": str(h.get("name", "")).strip()[:64],
                "buy_date": str(h.get("buy_date", ""))[:16],
                "cost": h.get("cost") if isinstance(h.get("cost"), (int, float)) else None,
                "position_pct": h.get("position_pct") if isinstance(h.get("position_pct"), (int, float)) else None,
                "note": str(h.get("note", ""))[:280],
            }
        )
    _save(user, clean)
    return jsonify(_load(user))


# ---------- 规范报告 ----------

def _build_report_prompt(data: dict) -> str:
    holdings = data.get("holdings", [])
    if not holdings:
        holdings_text = "（用户当前没有任何持仓记录）"
    else:
        rows = []
        for i, h in enumerate(holdings, 1):
            rows.append(
                f"{i}. {h.get('ticker', '?')}({h.get('name', '')}) {h.get('market', '')} "
                f"成本价 {h.get('cost', '—')} 仓位 {h.get('position_pct', '—')}% "
                f"买入日期 {h.get('buy_date') or '（未填）'} 备注\"{h.get('note') or '（空）'}\""
            )
        holdings_text = "\n".join(rows)

    return (
        "你是价值投资方法论助手。仅基于下面的「方法论核心」和「用户持仓」，生成一份中文 markdown 规范报告。\n\n"
        "要求：\n"
        "- 用方法论的视角审视每一笔持仓，明确指出缺失项（没有可证伪 thesis / 没有估值落地 / 没过 Pabrai 三问 / 没退出条件 / 缺成本或仓位）。\n"
        "- 不要给\"买入/卖出/目标价\"建议——这是一份审视流程与纪律的学习报告，不是荐股。\n"
        "- 结构固定为：## 组合总览 / ## 逐仓位审视 / ## 组合层面（集中度 + 区域配置 vs 美50-A30-加密≤5）/ ## 纪律与行为提醒 / ## 下一步该补什么（给可执行清单）。\n"
        "- 语言简洁、犀利、不客套。数据不足就直说\"数据不足以判断 X\"，不要编造数字。\n\n"
        f"{METHODOLOGY_CONTEXT}\n\n"
        f"【用户持仓】\n{holdings_text}\n"
    )


def _run_report_job(user: str, prompt: str) -> None:
    """Background thread; report gen takes ~30-90s. Writes result to DB."""
    if REPORT_MODE == "mock":
        time.sleep(2)
        _write_report_state(user, {"status": "done", "report": _MOCK_REPORT.format(n=len(prompt)), "generated_at": _now()})
        return
    try:
        r = subprocess.run(["hermes", "-z", prompt], capture_output=True, text=True, timeout=240)
        report = (r.stdout or "").strip()
        if r.returncode != 0 or not report:
            err = (r.stderr or "").strip()[-300:] or "hermes 返回空内容（可能需要刷新 codex 登录）"
            _write_report_state(user, {"status": "error", "error": err})
        else:
            _write_report_state(user, {"status": "done", "report": report, "generated_at": _now()})
    except subprocess.TimeoutExpired:
        _write_report_state(user, {"status": "error", "error": "生成超时（>240s）"})
    except FileNotFoundError:
        _write_report_state(user, {"status": "error", "error": "服务器未安装 hermes"})
    except Exception as e:  # noqa: BLE001
        _write_report_state(user, {"status": "error", "error": str(e)[:300]})


@app.get("/api/report")
def get_report():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    state = _read_report_state(user)
    if not state:
        return {"status": "none", "report": None, "can_push": user in FEISHU_USERS}
    state["can_push"] = user in FEISHU_USERS
    return jsonify(state)


@app.post("/api/report")
def gen_report():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    cur = _read_report_state(user)
    if cur and cur.get("status") == "running" and (time.time() - (cur.get("started_at") or 0) < 300):
        return {"status": "running"}
    _write_report_state(user, {"status": "running", "started_at": time.time()})
    prompt = _build_report_prompt(_load(user))
    threading.Thread(target=_run_report_job, args=(user, prompt), daemon=True).start()
    return {"status": "running"}


@app.post("/api/report/push")
def push_report():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    target = FEISHU_USERS.get(user)
    if not target:
        return {"error": "飞书推送暂未对该用户开通"}, 403
    state = _read_report_state(user) or {}
    report = state.get("report") or ""
    if state.get("status") != "done" or not report:
        return {"error": "请先生成报告"}, 400
    try:
        r = subprocess.run(
            ["hermes", "send", "--to", target, "--subject", "📊 价值投资 · 持仓规范报告"],
            input=report, capture_output=True, text=True, timeout=60,
        )
    except FileNotFoundError:
        return {"error": "hermes 不可用"}, 500
    except subprocess.TimeoutExpired:
        return {"error": "推送超时"}, 504
    if r.returncode != 0:
        return {"error": "推送失败：" + (r.stderr.strip()[-200:] or "unknown")}, 502
    return {"ok": True}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787, debug=True)
