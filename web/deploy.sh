#!/usr/bin/env bash
#
# web/deploy.sh — deploy the React SPA to the value-investment web root.
#
# Flow: vite build (with content sync) → rsync web/dist/ to the server web root.
# Server reached via the local SSH alias `openclaw` (defined in ~/.ssh/config;
# no IP / port / user is hard-coded here).
#
# ⚠️ This REPLACES the live vanilla site with the React SPA. It also requires the
#    SPA nginx vhost (server/nginx-value-investment-spa.conf) to be installed once,
#    so client-side routes fall back to /index.html. Run that one-time step first:
#       scp server/nginx-value-investment-spa.conf openclaw:/tmp/
#       ssh openclaw 'sudo cp /tmp/nginx-value-investment-spa.conf \
#         /etc/nginx/sites-available/value-investment && sudo nginx -t && sudo systemctl reload nginx'
#
# Usage:
#   chmod +x web/deploy.sh
#   ./web/deploy.sh            # build + sync
#   ./web/deploy.sh --dry-run  # show what rsync would change, transfer nothing
set -euo pipefail

REMOTE="openclaw:/var/www/value-investment/"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$HERE"

DRY=""
[[ "${1:-}" == "--dry-run" ]] && DRY="--dry-run"

command -v npm   >/dev/null 2>&1 || { echo "❌ npm not found"; exit 1; }
command -v rsync >/dev/null 2>&1 || { echo "❌ rsync not found"; exit 1; }

echo "🛠️  [1/2] building SPA (npm run build → sync-content + tsc + vite) ..."
npm run build
echo "✅ build done → web/dist/"

echo "📡 [2/2] syncing dist/ → ${REMOTE} ${DRY} ..."
rsync -avz --delete ${DRY} -e ssh dist/ "${REMOTE}"
echo "✅ ${DRY:+(dry run) }deploy complete."
