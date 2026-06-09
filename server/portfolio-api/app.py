#!/usr/bin/env python3
"""Portfolio input API for the value-investing system.

A tiny Flask service behind nginx (proxied at /api/). Provides:
  - access-code login (whitelist) → signed session cookie
  - per-user holdings storage (one JSON file per user)

Secrets live ONLY on the server (never in the repo):
  - VI_CODES_FILE   JSON mapping {access_code: username}  (e.g. /etc/value-investment/access-codes.json)
  - VI_SECRET_KEY   Flask session signing key
  - VI_DATA_DIR     where per-user holdings JSON files live

The public repo ships only access-codes.example.json (placeholders).
"""
from __future__ import annotations

import datetime
import json
import os
import re
import tempfile
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


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _codes() -> dict:
    try:
        return json.loads(CODES_FILE.read_text("utf-8"))
    except Exception:
        return {}


def _user_file(user: str) -> Path:
    safe = re.sub(r"[^a-z0-9_-]", "", user.lower())[:32] or "unknown"
    return DATA_DIR / f"holdings-{safe}.json"


def _load(user: str) -> dict:
    f = _user_file(user)
    if f.exists():
        try:
            return json.loads(f.read_text("utf-8"))
        except Exception:
            pass
    return {"holdings": [], "updated_at": None}


def _save(user: str, data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tmp = tempfile.NamedTemporaryFile("w", dir=DATA_DIR, delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.flush()
    os.fsync(tmp.fileno())
    tmp.close()
    os.replace(tmp.name, _user_file(user))


def _current_user() -> str | None:
    return session.get("user")


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


if __name__ == "__main__":
    # dev only; production runs under gunicorn via systemd
    app.run(host="127.0.0.1", port=8787, debug=True)
