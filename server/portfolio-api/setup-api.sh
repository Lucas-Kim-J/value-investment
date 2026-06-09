#!/usr/bin/env bash
# Install / update the portfolio input API on the server (run as root).
#   ssh openclaw 'bash -s' < server/portfolio-api/setup-api.sh
# or after rsync-ing server/ to the box:
#   ssh openclaw 'bash /root/vi-server/portfolio-api/setup-api.sh'
#
# Idempotent. Creates app + venv + systemd service + secret env.
# Does NOT write real access codes — create /etc/value-investment/access-codes.json
# separately so codes never live in any tracked file.
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
APP_DIR=/opt/value-investment-api
DATA_DIR=/var/lib/value-investment
ETC_DIR=/etc/value-investment

echo "== dirs =="
mkdir -p "$APP_DIR" "$DATA_DIR" "$ETC_DIR"
chmod 700 "$ETC_DIR"

echo "== app code =="
cp "$SRC/app.py" "$APP_DIR/app.py"

echo "== venv + deps =="
if [ ! -d "$APP_DIR/venv" ]; then
  python3 -m venv "$APP_DIR/venv"
fi
"$APP_DIR/venv/bin/pip" -q install --upgrade pip
"$APP_DIR/venv/bin/pip" -q install -r "$SRC/requirements.txt"

echo "== secret env =="
if [ ! -f "$ETC_DIR/api.env" ]; then
  SECRET="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
  cat > "$ETC_DIR/api.env" <<EOF
VI_SECRET_KEY=$SECRET
VI_DATA_DIR=$DATA_DIR
VI_CODES_FILE=$ETC_DIR/access-codes.json
EOF
  chmod 600 "$ETC_DIR/api.env"
  echo "   wrote $ETC_DIR/api.env (new secret)"
else
  echo "   $ETC_DIR/api.env exists (kept)"
fi

if [ ! -f "$ETC_DIR/access-codes.json" ]; then
  echo '{}' > "$ETC_DIR/access-codes.json"
  chmod 600 "$ETC_DIR/access-codes.json"
  echo "   wrote EMPTY $ETC_DIR/access-codes.json — add real codes separately!"
fi

echo "== systemd =="
cp "$SRC/value-investment-api.service" /etc/systemd/system/value-investment-api.service
systemctl daemon-reload
systemctl enable --now value-investment-api
systemctl restart value-investment-api
sleep 1

echo "== nginx vhost =="
if [ -f "$SRC/../nginx-value-investment.conf" ] && command -v nginx >/dev/null 2>&1; then
  cp "$SRC/../nginx-value-investment.conf" /etc/nginx/sites-available/value-investment
  ln -sf /etc/nginx/sites-available/value-investment /etc/nginx/sites-enabled/value-investment
  rm -f /etc/nginx/sites-enabled/default
  nginx -t && systemctl reload nginx && echo "   vhost installed + nginx reloaded"
else
  echo "   (skipped — nginx not found or conf missing)"
fi

echo "== health =="
curl -s http://127.0.0.1:8787/api/health && echo
echo "DONE"
