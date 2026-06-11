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

import base64
import datetime
import hashlib
import hmac
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from cryptography.fernet import Fernet
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
        # ---- v2: learning OS tables (all additive, never touch holdings/reports) ----
        cur.execute(
            """
            -- content seed tables (rebuildable from content/ via seed.py)
            CREATE TABLE IF NOT EXISTS glossary_terms (
                slug       TEXT PRIMARY KEY,
                term       TEXT NOT NULL,
                term_en    TEXT,
                category   TEXT,
                definition TEXT,
                detail_url TEXT,
                related    TEXT[]
            );
            CREATE TABLE IF NOT EXISTS canon_items (
                slug          TEXT PRIMARY KEY,
                source        TEXT,
                kind          TEXT,
                title         TEXT,
                period        TEXT,
                official_url  TEXT,
                coverage      TEXT,
                tier          TEXT,
                est_minutes   INTEGER,
                why           TEXT,
                guide         TEXT,
                questions     JSONB,
                related_terms TEXT[],
                sort_order    INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS achievements (
                key         TEXT PRIMARY KEY,
                title       TEXT,
                description TEXT,
                tier        INTEGER DEFAULT 1,
                icon        TEXT,
                rule        JSONB,
                sort_order  INTEGER DEFAULT 0
            );
            -- user data tables (never overwritten by seed)
            CREATE TABLE IF NOT EXISTS learning_events (
                id         BIGSERIAL PRIMARY KEY,
                username   TEXT NOT NULL,
                item_type  TEXT NOT NULL,      -- 'canon' | 'term' | 'methodology'
                item_slug  TEXT NOT NULL,
                action     TEXT NOT NULL,      -- 'read' | 'noted'
                detail     JSONB DEFAULT '{}',
                minutes    INTEGER DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_le_user ON learning_events(username, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_le_user_item ON learning_events(username, item_type, item_slug);
            CREATE TABLE IF NOT EXISTS user_term_mastery (
                username       TEXT NOT NULL,
                term_slug      TEXT NOT NULL,
                mastery        TEXT NOT NULL DEFAULT 'seen',  -- 'seen' | 'mastered'
                my_restatement TEXT,
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (username, term_slug)
            );
            CREATE TABLE IF NOT EXISTS user_achievements (
                username        TEXT NOT NULL,
                achievement_key TEXT NOT NULL,
                unlocked_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (username, achievement_key)
            );
            CREATE TABLE IF NOT EXISTS company_analyses (
                id           BIGSERIAL PRIMARY KEY,
                username     TEXT NOT NULL,
                market       TEXT,
                ticker       TEXT NOT NULL,
                company_name TEXT,
                status       TEXT NOT NULL DEFAULT 'running',
                report       TEXT,
                error        TEXT,
                profile_snap JSONB,
                started_at   DOUBLE PRECISION,
                generated_at TIMESTAMPTZ,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_ca_user ON company_analyses(username, created_at DESC);
            CREATE INDEX IF NOT EXISTS idx_ca_user_ticker ON company_analyses(username, ticker, created_at DESC);
            CREATE TABLE IF NOT EXISTS chat_turns (
                id         BIGSERIAL PRIMARY KEY,
                username   TEXT NOT NULL,
                status     TEXT NOT NULL DEFAULT 'running',
                question   TEXT,
                context    TEXT,
                reply      TEXT,
                error      TEXT,
                started_at DOUBLE PRECISION,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_chat_user ON chat_turns(username, created_at DESC);
            -- terms the user learned by selecting text + asking hermes ("划词学的").
            -- Kept SEPARATE from the curated glossary_terms — AI drafts, never masquerade as canon.
            CREATE TABLE IF NOT EXISTS user_terms (
                username   TEXT NOT NULL,
                slug       TEXT NOT NULL,
                term       TEXT NOT NULL,
                term_en    TEXT,
                definition TEXT,
                source     TEXT DEFAULT 'hermes',         -- provenance
                status     TEXT NOT NULL DEFAULT 'draft',  -- 'draft' | 'confirmed'
                context    TEXT,                           -- the sentence it was selected from
                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (username, slug)
            );
            -- async jobs for the inline 解释 card (same pattern as chat_turns)
            CREATE TABLE IF NOT EXISTS explain_jobs (
                id           BIGSERIAL PRIMARY KEY,
                username     TEXT NOT NULL,
                status       TEXT NOT NULL DEFAULT 'running',
                text         TEXT,
                context      TEXT,
                matched_slug TEXT,
                reply        TEXT,
                error        TEXT,
                started_at   DOUBLE PRECISION,
                created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            -- read-only exchange API keys (crypto portfolio import). api_secret is
            -- encrypted at rest (Fernet) — critical because pg_dump backups exist.
            CREATE TABLE IF NOT EXISTS exchange_keys (
                id             BIGSERIAL PRIMARY KEY,
                username       TEXT NOT NULL,
                exchange       TEXT NOT NULL,
                label          TEXT,
                api_key        TEXT NOT NULL,
                api_secret_enc TEXT NOT NULL,
                created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
            );
            CREATE INDEX IF NOT EXISTS idx_ek_user ON exchange_keys(username);
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
    _reap_stale("reports", user)
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


# ======================================================================
# v2: learning OS — canon library, terms wiki, learning trace, achievements,
# personalized company analysis. All additive; holdings/reports untouched.
# ======================================================================

RDC = psycopg2.extras.RealDictCursor


def _reap_stale(table: str, user: str) -> None:
    """Mark rows stuck in 'running' >5min as error (worker-restart orphans).
    `table` is a fixed literal ('company_analyses' / 'reports'), never user input."""
    try:
        with _db() as c, c.cursor() as cur:
            cur.execute(
                f"UPDATE {table} SET status='error', error=coalesce(nullif(error,''),'超时/任务中断') "
                "WHERE username=%s AND status='running' AND coalesce(started_at,0) < %s",
                (user, time.time() - 300),
            )
    except Exception:
        pass


def run_hermes(prompt: str) -> str:
    """Shared LLM runner. mock locally, real hermes on the server."""
    if REPORT_MODE == "mock":
        time.sleep(2)
        return f"## 分析（本地 mock）\n\n本地未调用 hermes（生产环境会用服务器上的 hermes 按方法论生成）。\nprompt 长度：{len(prompt)} 字符。"
    r = subprocess.run(["hermes", "-z", prompt], capture_output=True, text=True, timeout=240)
    out = (r.stdout or "").strip()
    if r.returncode != 0 or not out:
        raise RuntimeError((r.stderr or "").strip()[-300:] or "hermes 返回空内容")
    return out


# ---------- learner profile + achievements ----------

def _learner_stats(user: str) -> dict:
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT count(*) n FROM holdings WHERE username=%s", (user,)); holdings = cur.fetchone()["n"]
        cur.execute("SELECT count(DISTINCT item_slug) n FROM learning_events WHERE username=%s AND item_type='canon'", (user,)); canon_read = cur.fetchone()["n"]
        cur.execute("SELECT count(DISTINCT item_slug) n FROM learning_events WHERE username=%s AND item_type='canon' AND action='noted'", (user,)); canon_noted = cur.fetchone()["n"]
        cur.execute("""SELECT ci.tier tier, count(DISTINCT le.item_slug) n FROM learning_events le
                       JOIN canon_items ci ON ci.slug=le.item_slug
                       WHERE le.username=%s AND le.item_type='canon' AND le.action='noted' GROUP BY ci.tier""", (user,))
        noted_tier = {r["tier"]: r["n"] for r in cur.fetchall()}
        cur.execute("SELECT count(*) n FROM user_term_mastery WHERE username=%s AND mastery='mastered'", (user,)); term_mastered = cur.fetchone()["n"]
        cur.execute("SELECT count(*) n FROM company_analyses WHERE username=%s AND status='done'", (user,)); company_analyzed = cur.fetchone()["n"]
        cur.execute("SELECT count(DISTINCT market) n FROM company_analyses WHERE username=%s AND status='done' AND coalesce(market,'')<>''", (user,)); markets_analyzed = cur.fetchone()["n"]
        cur.execute("SELECT count(*) n FROM reports WHERE username=%s AND status='done'", (user,)); report_generated = cur.fetchone()["n"]
        cur.execute("SELECT coalesce(sum(minutes),0) m FROM learning_events WHERE username=%s", (user,)); total_min = cur.fetchone()["m"]
    return {"holdings": holdings, "canon_read": canon_read, "canon_noted": canon_noted, "canon_noted_tier": noted_tier,
            "term_mastered": term_mastered, "company_analyzed": company_analyzed, "markets_analyzed": markets_analyzed,
            "report_generated": report_generated, "total_min": total_min}


def _build_learner_profile(user: str) -> dict:
    s = _learner_stats(user)
    if s["canon_read"] < 2 and s["term_mastered"] < 3:
        stage = "novice"
    elif s["canon_read"] < 8:
        stage = "building"
    else:
        stage = "practitioner"
    with _db() as c, c.cursor() as cur:
        cur.execute("SELECT term_slug FROM user_term_mastery WHERE username=%s AND mastery='mastered'", (user,))
        mastered = [r[0] for r in cur.fetchall()]
    return {"stage": stage, "canon_read": s["canon_read"], "term_mastered": s["term_mastered"],
            "total_hours": round(s["total_min"] / 60, 1), "mastered_terms": mastered, "stats": s}


def _eval_rule(rule: dict, s: dict) -> bool:
    t = rule.get("type")
    if t == "any":
        return any(_eval_rule(r, s) for r in rule.get("of", []))
    gte = rule.get("gte", 1)
    if t == "canon_noted_tier":
        return s["canon_noted_tier"].get(rule.get("tier", ""), 0) >= gte
    return s.get(t, 0) >= gte


def _recheck_achievements(user: str) -> list:
    if not user:
        return []
    s = _learner_stats(user)
    newly = []
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT key, rule FROM achievements")
        defs = cur.fetchall()
        cur.execute("SELECT achievement_key FROM user_achievements WHERE username=%s", (user,))
        have = {r["achievement_key"] for r in cur.fetchall()}
        for d in defs:
            if d["key"] in have:
                continue
            rule = d["rule"] if isinstance(d["rule"], dict) else json.loads(d["rule"])
            if _eval_rule(rule, s):
                cur.execute("INSERT INTO user_achievements(username,achievement_key) VALUES (%s,%s) ON CONFLICT DO NOTHING", (user, d["key"]))
                newly.append(d["key"])
    return newly


# ---------- canon library ----------

@app.get("/api/canon")
def list_canon():
    user = _current_user()
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT slug,source,kind,title,period,official_url,coverage,tier,est_minutes,why,related_terms FROM canon_items ORDER BY tier,sort_order,slug")
        items = [dict(r) for r in cur.fetchall()]
        read = set()
        if user:
            cur.execute("SELECT DISTINCT item_slug FROM learning_events WHERE username=%s AND item_type='canon'", (user,))
            read = {r["item_slug"] for r in cur.fetchall()}
    for it in items:
        it["read"] = it["slug"] in read
    return jsonify({"items": items})


@app.get("/api/canon/<slug>")
def get_canon(slug):
    user = _current_user()
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT * FROM canon_items WHERE slug=%s", (slug,))
        item = cur.fetchone()
        if not item:
            return {"error": "not found"}, 404
        item = dict(item)
        events = []
        if user:
            cur.execute("SELECT action,detail,created_at FROM learning_events WHERE username=%s AND item_type='canon' AND item_slug=%s ORDER BY created_at", (user, slug))
            events = [{"action": r["action"], "detail": r["detail"], "created_at": r["created_at"].isoformat()} for r in cur.fetchall()]
    item["my_events"] = events
    return jsonify(item)


@app.post("/api/canon/<slug>/read")
def read_canon(slug):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    note = str(body.get("note", "")).strip()[:2000]
    minutes = int(body.get("minutes", 0) or 0)
    action = "noted" if note else "read"
    with _db() as c, c.cursor() as cur:
        cur.execute("INSERT INTO learning_events(username,item_type,item_slug,action,detail,minutes) VALUES (%s,'canon',%s,%s,%s,%s)",
                    (user, slug, action, json.dumps({"note": note}, ensure_ascii=False), minutes))
    return {"ok": True, "action": action, "new_achievements": _recheck_achievements(user)}


# ---------- terms wiki ----------

LEARNED_CATEGORY = "我划词学的（待整理）"
_SLUG_RE = re.compile(r"[^a-z0-9一-鿿]+")


def _slugify(s: str) -> str:
    s = _SLUG_RE.sub("-", (s or "").strip().lower()).strip("-")
    return s


def _match_curated_term(text: str) -> dict | None:
    """Find the curated glossary term a selection refers to (for grounding the
    explanation + linking to the authoritative card). Exact term/EN first, then substring."""
    t = (text or "").strip().lower()
    if not t:
        return None
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT slug,term,term_en,definition FROM glossary_terms")
        rows = [dict(r) for r in cur.fetchall()]
    for r in rows:
        if (r["term"] or "").lower() == t or (r["term_en"] or "").lower() == t:
            return r
    for r in rows:
        if r["term"] and r["term"] in text:
            return r
        if r["term_en"] and len(r["term_en"]) > 2 and r["term_en"].lower() in t:
            return r
    return None


@app.get("/api/terms")
def list_terms():
    user = _current_user()
    q = (request.args.get("q") or "").strip().lower()
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT slug,term,term_en,category,definition,detail_url,related FROM glossary_terms ORDER BY category,term")
        items = [dict(r) for r in cur.fetchall()]
        for t in items:
            t["learned"] = False
        mastery = {}
        if user:
            # the user's own 划词-learned terms (AI drafts) — appended as a distinct section
            cur.execute("SELECT slug,term,term_en,definition,status FROM user_terms WHERE username=%s ORDER BY created_at", (user,))
            for r in cur.fetchall():
                d = dict(r)
                d.update(category=LEARNED_CATEGORY, detail_url=None, related=[], learned=True)
                items.append(d)
            cur.execute("SELECT term_slug,mastery FROM user_term_mastery WHERE username=%s", (user,))
            mastery = {r["term_slug"]: r["mastery"] for r in cur.fetchall()}
    if q:
        items = [t for t in items if q in (t["term"] or "").lower() or q in (t["term_en"] or "").lower() or q in (t["slug"] or "")]
    for t in items:
        t["mastery"] = mastery.get(t["slug"], "")
    return jsonify({"items": items})


@app.get("/api/terms/<slug>")
def get_term(slug):
    user = _current_user()
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT slug,term,term_en,category,definition,detail_url,related FROM glossary_terms WHERE slug=%s", (slug,))
        t = cur.fetchone()
        if t:
            t = dict(t)
            t["learned"] = False
        else:  # fall back to the user's own 划词-learned terms
            if not user:
                return {"error": "not found"}, 404
            cur.execute("SELECT slug,term,term_en,definition,status,context FROM user_terms WHERE username=%s AND slug=%s", (user, slug))
            ut = cur.fetchone()
            if not ut:
                return {"error": "not found"}, 404
            t = dict(ut)
            t.update(category=LEARNED_CATEGORY, detail_url=None, related=[], learned=True)
        t["mastery"] = ""
        t["my_restatement"] = ""
        if user:
            cur.execute("SELECT mastery,my_restatement FROM user_term_mastery WHERE username=%s AND term_slug=%s", (user, slug))
            m = cur.fetchone()
            if m:
                t["mastery"], t["my_restatement"] = m["mastery"], m["my_restatement"] or ""
        # connective tissue: which canon pieces reference this term
        cur.execute("SELECT slug,title FROM canon_items WHERE %s = ANY(related_terms) ORDER BY sort_order LIMIT 6", (slug,))
        t["appears_in"] = [dict(r) for r in cur.fetchall()]
    return jsonify(t)


@app.post("/api/terms/learned")
def save_learned_term():
    """Persist a 划词-explained term into the user's wiki as an AI draft (待核实)."""
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    term = str(body.get("term", "")).strip()[:120]
    term_en = str(body.get("term_en", "")).strip()[:120]
    definition = str(body.get("definition", "")).strip()[:4000]
    context = str(body.get("context", "")).strip()[:1000]
    if not term:
        return {"error": "缺少术语"}, 400
    if not definition:
        return {"error": "解释还没生成完，请稍候再收藏"}, 400
    slug = _slugify(term)
    if not slug:
        return {"error": "无法识别这个术语"}, 400
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT slug FROM glossary_terms WHERE slug=%s", (slug,))
        if cur.fetchone():  # already a curated term — point the user there instead of duplicating
            return {"ok": True, "slug": slug, "curated": True, "new_achievements": []}
        cur.execute(
            """INSERT INTO user_terms(username,slug,term,term_en,definition,source,status,context)
               VALUES (%s,%s,%s,%s,%s,'hermes','draft',%s)
               ON CONFLICT (username,slug) DO UPDATE SET
                 term=EXCLUDED.term, term_en=EXCLUDED.term_en, definition=EXCLUDED.definition, context=EXCLUDED.context""",
            (user, slug, term, term_en, definition, context))
        cur.execute("INSERT INTO learning_events(username,item_type,item_slug,action,detail,minutes) VALUES (%s,'term',%s,'learned',%s,0)",
                    (user, slug, json.dumps({"term": term, "source": "划词"}, ensure_ascii=False)))
    return {"ok": True, "slug": slug, "curated": False, "new_achievements": _recheck_achievements(user)}


@app.put("/api/terms/<slug>/mastery")
def set_mastery(slug):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    mastery = body.get("mastery", "seen")
    if mastery not in ("seen", "mastered"):
        return {"error": "bad mastery"}, 400
    restatement = str(body.get("restatement", "")).strip()[:1000]
    if mastery == "mastered" and len(restatement) < 8:
        return {"error": "请用自己的话复述这个术语（至少一句）——讲得出才算掌握"}, 400
    with _db() as c, c.cursor() as cur:
        cur.execute("""INSERT INTO user_term_mastery(username,term_slug,mastery,my_restatement,updated_at)
            VALUES (%s,%s,%s,%s,now()) ON CONFLICT (username,term_slug)
            DO UPDATE SET mastery=EXCLUDED.mastery, my_restatement=EXCLUDED.my_restatement, updated_at=now()""",
            (user, slug, mastery, restatement))
    return {"ok": True, "mastery": mastery, "new_achievements": _recheck_achievements(user)}


# ---------- learning summary + achievements ----------

@app.get("/api/learning/summary")
def learning_summary():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    p = _build_learner_profile(user)
    return jsonify({"stage": p["stage"], "canon_read": p["canon_read"], "term_mastered": p["term_mastered"],
                    "total_hours": p["total_hours"], "stats": p["stats"]})


@app.get("/api/achievements")
def list_achievements():
    user = _current_user()
    if user:
        _recheck_achievements(user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT key,title,description,tier,icon FROM achievements ORDER BY tier,sort_order,key")
        defs = [dict(r) for r in cur.fetchall()]
        have = {}
        if user:
            cur.execute("SELECT achievement_key,unlocked_at FROM user_achievements WHERE username=%s", (user,))
            have = {r["achievement_key"]: r["unlocked_at"].isoformat() for r in cur.fetchall()}
    for d in defs:
        d["unlocked"] = d["key"] in have
        d["unlocked_at"] = have.get(d["key"])
    return jsonify({"items": defs, "unlocked_count": len(have)})


# ---------- company analysis (one-click + archive) ----------

def compose_analysis_prompt(user: str, company: dict) -> str:
    p = _build_learner_profile(user)
    if p["stage"] == "novice":
        stance = "用户是新手（一手内容读得还少）。多解释*为什么*，每用一个术语就一句话点明定义；强调先验证再深研；不要假设他懂反向 DCF / Owner Earnings。"
    elif p["stage"] == "building":
        stance = "用户在建体系期。可直接用已掌握的术语，对未掌握的补一句定义；重点放在四工具三角验证的落地。"
    else:
        stance = "用户是进阶者。术语直接用、不解释；拔高到组合层面与 thesis 可证伪性，犀利、省略基础。"
    mastered = "、".join(p["mastered_terms"][:30]) or "（暂无）"
    return (
        f"{METHODOLOGY_CONTEXT}\n\n"
        f"【用户学习画像】阶段={p['stage']} 已读一手内容={p['canon_read']} 已掌握术语：{mastered}\n\n"
        f"【交流策略】{stance}\n\n"
        f"【本次分析公司】{company.get('ticker')} {company.get('name', '')} 市场={company.get('market', '')}\n"
        "任务：按价值投资方法论对这家公司做一次审视报告。结构固定为："
        "## 生意是什么 / ## 护城河与质量 / ## 该看哪些估值信号（四工具）/ ## 风险与价值陷阱红旗 / ## 我该补哪些验证（Pabrai 三问 + 可证伪 thesis + 退出条件）。\n"
        "硬约束：不给买卖建议/目标价；**绝不编造任何具体财务数字**——涉及数字一律写「→ 去官方原文核对」；数据不足就说数据不足，不要编。"
    )


def _run_analysis_job(analysis_id: int, prompt: str) -> None:
    try:
        report = run_hermes(prompt)
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE company_analyses SET status='done', report=%s, generated_at=now() WHERE id=%s", (report, analysis_id))
    except subprocess.TimeoutExpired:
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE company_analyses SET status='error', error='生成超时（>240s）' WHERE id=%s", (analysis_id,))
    except Exception as e:  # noqa: BLE001
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE company_analyses SET status='error', error=%s WHERE id=%s", (str(e)[:300], analysis_id))


@app.post("/api/analyses")
def start_analysis():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    ticker = str(body.get("ticker", "")).strip()[:32]
    if not ticker:
        return {"error": "缺 ticker / 公司代码"}, 400
    market = str(body.get("market", ""))[:16]
    name = str(body.get("name", ""))[:64]
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,started_at FROM company_analyses WHERE username=%s AND ticker=%s AND status='running' ORDER BY id DESC LIMIT 1", (user, ticker))
        run = cur.fetchone()
        if run and run["started_at"] and time.time() - run["started_at"] < 300:
            return {"id": run["id"], "status": "running"}
    profile = _build_learner_profile(user)
    prompt = compose_analysis_prompt(user, {"ticker": ticker, "name": name, "market": market})
    with _db() as c, c.cursor() as cur:
        cur.execute("""INSERT INTO company_analyses(username,market,ticker,company_name,status,profile_snap,started_at)
            VALUES (%s,%s,%s,%s,'running',%s,%s) RETURNING id""",
            (user, market, ticker, name, json.dumps({"stage": profile["stage"]}), time.time()))
        aid = cur.fetchone()[0]
    threading.Thread(target=_run_analysis_job, args=(aid, prompt), daemon=True).start()
    return {"id": aid, "status": "running"}


@app.get("/api/analyses")
def list_analyses():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    _reap_stale("company_analyses", user)
    ticker = request.args.get("ticker")
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        if ticker:
            cur.execute("SELECT id,market,ticker,company_name,status,created_at,generated_at FROM company_analyses WHERE username=%s AND ticker=%s ORDER BY created_at DESC", (user, ticker))
        else:
            cur.execute("SELECT DISTINCT ON (ticker) id,market,ticker,company_name,status,created_at,generated_at FROM company_analyses WHERE username=%s ORDER BY ticker, created_at DESC", (user,))
        rows = []
        for r in cur.fetchall():
            d = dict(r)
            d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
            d["generated_at"] = d["generated_at"].isoformat() if d.get("generated_at") else None
            rows.append(d)
    return jsonify({"items": rows})


@app.get("/api/analyses/<int:aid>")
def get_analysis(aid):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    _reap_stale("company_analyses", user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,username,market,ticker,company_name,status,report,error,created_at,generated_at FROM company_analyses WHERE id=%s", (aid,))
        r = cur.fetchone()
    if not r or r["username"] != user:
        return {"error": "not found"}, 404
    d = dict(r)
    d.pop("username", None)
    d["created_at"] = d["created_at"].isoformat() if d.get("created_at") else None
    d["generated_at"] = d["generated_at"].isoformat() if d.get("generated_at") else None
    return jsonify(d)


# ---------- hermes chat (global learning companion) ----------

def compose_chat_prompt(user: str, question: str, context: str, history: list) -> str:
    p = _build_learner_profile(user)
    stage_note = {
        "novice": "用户是新手，多解释、少堆术语、鼓励先打基础。",
        "building": "用户在建体系，可直接用他已掌握的术语，对未掌握的补一句定义。",
        "practitioner": "用户进阶，直接、犀利、省略基础。",
    }.get(p["stage"], "")
    hist = "\n".join(f"用户：{h['q']}\nhermes：{h['r']}" for h in history[-5:] if h.get("r"))
    ctx = f"\n【用户正在看的页面内容 / 选中文字】\n{context}\n" if context else ""
    return (
        "你是 hermes，这个用户的价值投资学习伙伴。用中文、简洁、像同行对话。"
        "目标是帮他真正学懂：多用反问引导、鼓励他用自己的话复述、必要时关联他的方法论与持仓。\n"
        "如果给了他正在看的页面内容，请据此 + 他的学习阶段给出有依据的建议（比如先读/先做哪个、顺序、为什么），优先推荐「起点必读」和短而高杠杆的内容；不要泛泛而谈。\n"
        "硬约束：不荐股、不给目标价；**绝不编造具体财务数字**（涉及具体数字就提示「去官方原文核对」）；不知道就说不知道。回答控制在 250 字内，除非他要求展开。\n\n"
        f"{METHODOLOGY_CONTEXT}\n\n"
        f"【用户画像】阶段={p['stage']}；已掌握术语：{('、'.join(p['mastered_terms'][:20]) or '暂无')}。{stage_note}\n"
        f"{ctx}"
        + (f"\n【最近对话】\n{hist}\n" if hist else "")
        + f"\n用户：{question}\nhermes："
    )


def _run_chat_job(turn_id: int, prompt: str) -> None:
    try:
        reply = run_hermes(prompt)
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE chat_turns SET status='done', reply=%s WHERE id=%s", (reply, turn_id))
    except subprocess.TimeoutExpired:
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE chat_turns SET status='error', error='思考超时，请重试' WHERE id=%s", (turn_id,))
    except Exception as e:  # noqa: BLE001
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE chat_turns SET status='error', error=%s WHERE id=%s", (str(e)[:300], turn_id))


@app.get("/api/chat")
def chat_history():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,status,question,context,reply,error,created_at FROM chat_turns WHERE username=%s ORDER BY id DESC LIMIT 16", (user,))
        rows = list(cur.fetchall())[::-1]
    items = [{"id": r["id"], "status": r["status"], "question": r["question"], "context": r["context"],
              "reply": r["reply"], "error": r["error"]} for r in rows]
    return jsonify({"items": items})


@app.post("/api/chat")
def chat_send():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    question = str(body.get("question", "")).strip()[:2000]
    context = str(body.get("context", "")).strip()[:6000]  # large enough for a page digest ("看这一页")
    if not question:
        return {"error": "请输入问题"}, 400
    _reap_stale("chat_turns", user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT question q, reply r FROM chat_turns WHERE username=%s AND status='done' ORDER BY id DESC LIMIT 5", (user,))
        history = list(cur.fetchall())[::-1]
        cur.execute("INSERT INTO chat_turns(username,status,question,context,started_at) VALUES (%s,'running',%s,%s,%s) RETURNING id",
                    (user, question, context, time.time()))
        tid = cur.fetchone()["id"]
    prompt = compose_chat_prompt(user, question, context, history)
    threading.Thread(target=_run_chat_job, args=(tid, prompt), daemon=True).start()
    return {"id": tid, "status": "running"}


@app.get("/api/chat/<int:tid>")
def chat_poll(tid):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    _reap_stale("chat_turns", user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,username,status,question,reply,error FROM chat_turns WHERE id=%s", (tid,))
        r = cur.fetchone()
    if not r or r["username"] != user:
        return {"error": "not found"}, 404
    return jsonify({"id": r["id"], "status": r["status"], "question": r["question"], "reply": r["reply"], "error": r["error"]})


# ---------- inline 解释 (划词 → hermes explanation card) ----------

def compose_explain_prompt(user: str, text: str, context: str, curated: dict | None) -> str:
    p = _build_learner_profile(user)
    stage_note = {
        "novice": "用户是新手，讲得再朴素一点，少堆术语。",
        "building": "用户在建体系，可以关联他已掌握的术语。",
        "practitioner": "用户进阶，直接、精炼。",
    }.get(p["stage"], "")
    grounding = ""
    if curated:
        grounding = (f"\n【术语库已有权威定义，请以它为准、不要偏离它的含义】"
                     f"{curated['term']}（{curated.get('term_en') or ''}）：{curated.get('definition') or ''}\n")
    ctx = f"\n【这个词出现在这句话里】「{context}」\n" if context else ""
    return (
        "你是 hermes，这个用户的价值投资学习伙伴。他在阅读时划选了一个词/短语，请用中文给一个简短、好懂的解释。\n"
        "结构：① 一句话说清它是什么；② 一句它在价值投资里怎么用 / 为什么重要；③ 如果合适，给一个简短的例子或类比。\n"
        "硬约束：**绝不编造具体财务数字、业绩或引文**（涉及具体数字就提示「需去官方原文核对」）；不荐股、不给目标价；不确定就直说不知道。"
        "全文控制在 180 字内，朴素、不卖弄。\n\n"
        f"{grounding}{ctx}"
        f"【用户阶段】{p['stage']}。{stage_note}\n"
        f"\n要解释的词：「{text}」\nhermes 的解释："
    )


def _run_explain_job(job_id: int, prompt: str) -> None:
    try:
        reply = run_hermes(prompt)
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE explain_jobs SET status='done', reply=%s WHERE id=%s", (reply, job_id))
    except subprocess.TimeoutExpired:
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE explain_jobs SET status='error', error='思考超时，请重试' WHERE id=%s", (job_id,))
    except Exception as e:  # noqa: BLE001
        with _db() as c, c.cursor() as cur:
            cur.execute("UPDATE explain_jobs SET status='error', error=%s WHERE id=%s", (str(e)[:300], job_id))


@app.post("/api/explain")
def explain_send():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    text = str(body.get("text", "")).strip()[:200]
    context = str(body.get("context", "")).strip()[:1000]
    if not text:
        return {"error": "没有选中文字"}, 400
    curated = _match_curated_term(text)
    _reap_stale("explain_jobs", user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("INSERT INTO explain_jobs(username,status,text,context,matched_slug,started_at) VALUES (%s,'running',%s,%s,%s,%s) RETURNING id",
                    (user, text, context, (curated or {}).get("slug"), time.time()))
        jid = cur.fetchone()["id"]
    prompt = compose_explain_prompt(user, text, context, curated)
    threading.Thread(target=_run_explain_job, args=(jid, prompt), daemon=True).start()
    return {"id": jid, "status": "running", "curated": curated}


@app.get("/api/explain/<int:jid>")
def explain_poll(jid):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    _reap_stale("explain_jobs", user)
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,username,status,text,reply,error FROM explain_jobs WHERE id=%s", (jid,))
        r = cur.fetchone()
    if not r or r["username"] != user:
        return {"error": "not found"}, 404
    return jsonify({"id": r["id"], "status": r["status"], "text": r["text"], "reply": r["reply"], "error": r["error"]})


# ---------- crypto exchange import (read-only) ----------

SUPPORTED_EXCHANGES = {"gate": "Gate.io"}  # others scaffolded in the UI, not yet wired
GATE_HOST = "https://api.gateio.ws"
_STABLES = {"USDT", "USDC", "DAI", "BUSD", "TUSD", "FDUSD"}
_DUST_USD = 1.0  # hide / skip assets worth less than this (USD)


def _fernet() -> Fernet:
    # derive a Fernet key from the existing session secret — no extra env var,
    # and secrets in the DB / pg_dump backups are never plaintext.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(app.secret_key.encode()).digest()))


def _enc_secret(s: str) -> str:
    return _fernet().encrypt(s.encode()).decode()


def _dec_secret(s: str) -> str:
    return _fernet().decrypt(s.encode()).decode()


def _http_get_json(url: str, headers: dict, timeout: int = 12):
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")
        raise RuntimeError(f"HTTP {e.code}: {body[:160]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"网络错误：{getattr(e, 'reason', e)}")


def _gate_headers(key: str, secret: str, method: str, path: str, query: str = "", body: str = "") -> dict:
    t = str(int(time.time()))
    payload_hash = hashlib.sha512((body or "").encode()).hexdigest()
    sig_str = f"{method}\n{path}\n{query}\n{payload_hash}\n{t}"
    sign = hmac.new(secret.encode(), sig_str.encode(), hashlib.sha512).hexdigest()
    return {"KEY": key, "Timestamp": t, "SIGN": sign, "Accept": "application/json", "Content-Type": "application/json"}


def _gate_get(key: str, secret: str, path: str, query: str = ""):
    full = "/api/v4" + path
    headers = _gate_headers(key, secret, "GET", full, query)
    url = GATE_HOST + full + (("?" + query) if query else "")
    return _http_get_json(url, headers)


def _gate_public_get(path: str, query: str = ""):
    url = GATE_HOST + "/api/v4" + path + (("?" + query) if query else "")
    return _http_get_json(url, {"Accept": "application/json"})


def gate_snapshot(key: str, secret: str) -> dict:
    """Read-only portfolio snapshot from Gate.io v4."""
    total = _gate_get(key, secret, "/wallet/total_balance", "currency=USDT")  # also validates the key
    by_account = {}
    for name, v in (total.get("details") or {}).items():
        amt = float(v.get("amount") or 0)
        if amt > 0.5:
            by_account[name] = round(amt, 2)
    total_usdt = round(float((total.get("total") or {}).get("amount") or 0), 2)
    # spot prices (public) for per-coin USD valuation
    prices = {}
    try:
        for tk in _gate_public_get("/spot/tickers"):
            prices[tk.get("currency_pair")] = float(tk.get("last") or 0)
    except Exception:  # noqa: BLE001
        pass

    def usd(coin, amt):
        if coin in _STABLES:
            return amt
        return amt * (prices.get(coin + "_USDT") or 0)

    spot = []
    try:
        for b in _gate_get(key, secret, "/spot/accounts"):
            amt = float(b.get("available") or 0) + float(b.get("locked") or 0)
            if amt <= 0:
                continue
            coin = b.get("currency")
            u = usd(coin, amt)
            if u < _DUST_USD:  # hide sub-$1 dust
                continue
            spot.append({"coin": coin, "amount": amt, "usd": round(u, 2)})
    except Exception:  # noqa: BLE001
        pass
    spot.sort(key=lambda x: x["usd"], reverse=True)

    futures = []
    try:
        for p in _gate_get(key, secret, "/futures/usdt/positions"):
            size = float(p.get("size") or 0)
            if size == 0:
                continue
            futures.append({
                "contract": p.get("contract"), "size": size,
                "value": round(float(p.get("value") or 0), 2),
                "upnl": round(float(p.get("unrealised_pnl") or 0), 2),
                "entry": float(p.get("entry_price") or 0), "mark": float(p.get("mark_price") or 0),
            })
    except Exception:  # noqa: BLE001
        pass  # futures may be disabled / empty

    # 理财 / Earn holdings (itemizes the wallet's `finance` bucket; needs Earn read perm)
    finance = []
    try:
        for l in _gate_get(key, secret, "/earn/uni/lends"):  # 活期 / Simple Earn
            coin = l.get("currency"); amt = float(l.get("amount") or 0); u = usd(coin, amt)
            if amt > 0 and u >= _DUST_USD:
                finance.append({"coin": coin, "amount": amt, "usd": round(u, 2), "product": "活期"})
    except Exception:  # noqa: BLE001
        pass
    try:
        for d in _gate_get(key, secret, "/earn/dual/orders"):  # 双币赢 (open only)
            if d.get("status") not in ("INIT", "SETTLEMENT_PROCESSING"):
                continue
            coin = d.get("invest_currency"); amt = float(d.get("invest_amount") or 0); u = usd(coin, amt)
            if u >= _DUST_USD:
                finance.append({"coin": coin, "amount": amt, "usd": round(u, 2), "product": "双币"})
    except Exception:  # noqa: BLE001
        pass
    try:
        for st in _gate_get(key, secret, "/earn/structured/orders"):  # 结构化 (active)
            if st.get("status") != "SUCCESS":
                continue
            coin = st.get("lock_coin"); amt = float(st.get("amount") or 0); u = usd(coin, amt)
            if u >= _DUST_USD:
                finance.append({"coin": coin, "amount": amt, "usd": round(u, 2), "product": "结构化"})
    except Exception:  # noqa: BLE001
        pass
    finance.sort(key=lambda x: x["usd"], reverse=True)

    # TradFi (MT5) account — its equity is NOT in /wallet/total_balance, add it separately
    tradfi = 0.0
    try:
        ta = _gate_get(key, secret, "/tradfi/users/assets")
        tradfi = round(float((ta.get("data") or {}).get("equity") or 0), 2)
    except Exception:  # noqa: BLE001
        pass
    if tradfi >= _DUST_USD:
        by_account["tradfi"] = tradfi

    grand_total = round(total_usdt + tradfi, 2)  # wallet rollup already covers spot+finance; tradfi is extra
    return {"total_usdt": grand_total, "wallet_usdt": total_usdt, "tradfi_usdt": tradfi,
            "by_account": by_account, "spot": spot, "finance": finance, "futures": futures}


def fetch_exchange_snapshot(exchange: str, key: str, secret: str) -> dict:
    if exchange == "gate":
        return gate_snapshot(key, secret)
    raise RuntimeError("暂不支持该交易所")


@app.get("/api/exchange/keys")
def list_exchange_keys():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT id,exchange,label,api_key,created_at FROM exchange_keys WHERE username=%s ORDER BY id", (user,))
        rows = cur.fetchall()
    items = [{
        "id": r["id"], "exchange": r["exchange"], "label": r["label"],
        "key_masked": (r["api_key"][:5] + "…" + r["api_key"][-4:]) if len(r["api_key"] or "") > 11 else "••••",
        "created_at": r["created_at"].isoformat() if r["created_at"] else None,
    } for r in rows]
    return jsonify({"items": items, "supported": SUPPORTED_EXCHANGES})


@app.post("/api/exchange/keys")
def add_exchange_key():
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    body = request.get_json(force=True, silent=True) or {}
    exchange = str(body.get("exchange", "")).strip().lower()
    api_key = str(body.get("api_key", "")).strip()
    api_secret = str(body.get("api_secret", "")).strip()
    label = str(body.get("label", "")).strip()[:60]
    if exchange not in SUPPORTED_EXCHANGES:
        return {"error": "目前只支持 Gate.io"}, 400
    if not api_key or not api_secret:
        return {"error": "缺少 API key 或 secret"}, 400
    # validate the key by doing one read before saving
    try:
        fetch_exchange_snapshot(exchange, api_key, api_secret)
    except Exception as e:  # noqa: BLE001
        return {"error": "连接失败（请确认 key 正确、已开只读权限）：" + str(e)[:160]}, 400
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("INSERT INTO exchange_keys(username,exchange,label,api_key,api_secret_enc) VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (user, exchange, label or SUPPORTED_EXCHANGES[exchange], api_key, _enc_secret(api_secret)))
        kid = cur.fetchone()["id"]
    return {"ok": True, "id": kid}


@app.delete("/api/exchange/keys/<int:kid>")
def del_exchange_key(kid):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    with _db() as c, c.cursor() as cur:
        cur.execute("DELETE FROM exchange_keys WHERE id=%s AND username=%s", (kid, user))
    return {"ok": True}


def _load_key_row(user, kid):
    with _db() as c, c.cursor(cursor_factory=RDC) as cur:
        cur.execute("SELECT exchange,api_key,api_secret_enc FROM exchange_keys WHERE id=%s AND username=%s", (kid, user))
        return cur.fetchone()


@app.post("/api/exchange/keys/<int:kid>/sync")
def sync_exchange(kid):
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    r = _load_key_row(user, kid)
    if not r:
        return {"error": "not found"}, 404
    try:
        snap = fetch_exchange_snapshot(r["exchange"], r["api_key"], _dec_secret(r["api_secret_enc"]))
    except Exception as e:  # noqa: BLE001
        return {"error": "同步失败：" + str(e)[:200]}, 502
    return jsonify({"snapshot": snap})


@app.post("/api/exchange/keys/<int:kid>/import")
def import_exchange(kid):
    """Add the snapshot's spot coins (+ futures) into the user's holdings table
    (market=加密), deduped by ticker — never clobbers existing manual rows."""
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    r = _load_key_row(user, kid)
    if not r:
        return {"error": "not found"}, 404
    try:
        snap = fetch_exchange_snapshot(r["exchange"], r["api_key"], _dec_secret(r["api_secret_enc"]))
    except Exception as e:  # noqa: BLE001
        return {"error": "同步失败：" + str(e)[:200]}, 502
    existing = _load(user)["holdings"]
    have = {(h.get("ticker") or "").upper() for h in existing}
    src = SUPPORTED_EXCHANGES.get(r["exchange"], r["exchange"])
    added = 0
    rows = list(existing)
    today = datetime.date.today().isoformat()
    for area, items in (("现货", snap.get("spot", [])), ("理财", snap.get("finance", []))):
        for s in items:
            if s["usd"] < _DUST_USD:
                continue
            tk = (s["coin"] or "").upper()
            if not tk or tk in have:
                continue
            rows.append({"market": "加密", "ticker": tk, "name": f"{src} {area}",
                         "buy_date": None, "cost": None, "position_pct": None,
                         "note": f"{src}{area} {round(s['amount'], 6)} {tk} ≈ ${s['usd']}（{today} 同步）"})
            have.add(tk); added += 1
    if added:
        _save(user, rows)
    return {"ok": True, "added": added}


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8787, debug=True)
