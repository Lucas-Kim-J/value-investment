#!/usr/bin/env python3
"""Portfolio input API for the value-investing system.

A tiny Flask service behind nginx (proxied at /api/). Provides:
  - access-code login (whitelist) → signed session cookie
  - per-user holdings storage (one JSON file per user)
  - on-demand 规范报告 generation via the server's `hermes` agent
  - optional push of the report to Feishu (for whitelisted users)

Secrets live ONLY on the server (never in the repo):
  - VI_CODES_FILE   JSON mapping {access_code: username}
  - VI_SECRET_KEY   Flask session signing key
  - VI_DATA_DIR     where per-user holdings/report files live
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from flask import Flask, jsonify, request, session

DATA_DIR = Path(os.environ.get("VI_DATA_DIR", "/var/lib/value-investment"))
CODES_FILE = Path(os.environ.get("VI_CODES_FILE", "/etc/value-investment/access-codes.json"))

app = Flask(__name__)
app.secret_key = os.environ.get("VI_SECRET_KEY", "dev-insecure-change-me")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=30),
)

# Users whose generated report may be pushed to *their own* Feishu.
# (hermes' Feishu home channel currently belongs to lucas only.)
FEISHU_USERS = {"lucas": "feishu"}

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


def _safe(user: str) -> str:
    return re.sub(r"[^a-z0-9_-]", "", user.lower())[:32] or "unknown"


def _user_file(user: str) -> Path:
    return DATA_DIR / f"holdings-{_safe(user)}.json"


def _report_file(user: str) -> Path:
    return DATA_DIR / f"report-{_safe(user)}.json"


def _load(user: str) -> dict:
    f = _user_file(user)
    if f.exists():
        try:
            return json.loads(f.read_text("utf-8"))
        except Exception:
            pass
    return {"holdings": [], "updated_at": None}


def _backup(path: Path, prefix: str) -> None:
    """Keep a timestamped copy before overwriting, so data is never silently lost.
    Retains the newest 50 backups per prefix."""
    try:
        bdir = DATA_DIR / "backups"
        bdir.mkdir(exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d-%H%M%S")
        shutil.copy2(path, bdir / f"{prefix}-{ts}.json")
        for old in sorted(bdir.glob(f"{prefix}-*.json"))[:-50]:
            old.unlink(missing_ok=True)
    except Exception:
        pass


def _save(user: str, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    f = _user_file(user)
    if f.exists():
        _backup(f, f"holdings-{_safe(user)}")
    tmp = tempfile.NamedTemporaryFile("w", dir=DATA_DIR, delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.flush()
    os.fsync(tmp.fileno())
    tmp.close()
    os.replace(tmp.name, f)


def _current_user() -> str | None:
    return session.get("user")


# ---------- auth ----------

@app.get("/api/health")
def health():
    return {"ok": True, "time": _now()}


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
    data = {"holdings": clean, "updated_at": _now()}
    _save(user, data)
    return jsonify(data)


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


def _write_report_state(user: str, state: dict) -> None:
    state.setdefault("can_push", user in FEISHU_USERS)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    _report_file(user).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_report_state(user: str) -> dict | None:
    rf = _report_file(user)
    if rf.exists():
        try:
            return json.loads(rf.read_text("utf-8"))
        except Exception:
            pass
    return None


def _run_report_job(user: str, prompt: str) -> None:
    """Runs in a background thread; report gen takes ~30-90s. Writes result to the
    per-user report file so polling GETs (possibly on another worker) can read it."""
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
    """Current report state: {status: none|running|done|error, report?, error?, ...}."""
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    state = _read_report_state(user)
    if not state:
        return {"status": "none", "report": None, "can_push": user in FEISHU_USERS}
    state.setdefault("can_push", user in FEISHU_USERS)
    return jsonify(state)


@app.post("/api/report")
def gen_report():
    """Kick off async generation; returns immediately. Poll GET /api/report for result."""
    user = _current_user()
    if not user:
        return {"error": "未登录"}, 401
    cur = _read_report_state(user)
    if cur and cur.get("status") == "running" and (time.time() - cur.get("started_at", 0) < 300):
        return {"status": "running"}  # already generating
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
