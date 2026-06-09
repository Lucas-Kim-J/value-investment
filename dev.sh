#!/usr/bin/env bash
# One-command local dev: build the static site, then start postgres + api + nginx.
set -euo pipefail
cd "$(dirname "$0")"

echo "📦 building static site (markdown → html)..."
python3 build.py

echo "🐳 starting docker compose (db + api + web)..."
docker compose up --build -d

echo
echo "✅ local dev running:"
echo "   site   → http://localhost:8080/"
echo "   login  → http://localhost:8080/login.html   (codes: dev / lucas-dev)"
echo "   logs   → docker compose logs -f"
echo "   stop   → docker compose down   (data persists; 'down -v' wipes the local DB)"
