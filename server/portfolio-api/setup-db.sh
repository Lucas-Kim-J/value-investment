#!/usr/bin/env bash
# Provision PostgreSQL for the input portal + install nightly pg_dump backups.
# Idempotent. Run as root on the server BEFORE setup-api.sh:
#   ssh openclaw 'bash /root/vi-server/portfolio-api/setup-db.sh'
#
# Real DB password lives ONLY in /etc/value-investment/api.env (VI_DATABASE_URL).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
ETC_DIR=/etc/value-investment
APP_DIR=/opt/value-investment-api
BACKUP_DIR=/var/backups/value-investment
mkdir -p "$ETC_DIR" "$APP_DIR" "$BACKUP_DIR"
chmod 700 "$ETC_DIR"

echo "== install postgresql =="
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq postgresql >/dev/null 2>&1 || true
systemctl enable --now postgresql >/dev/null 2>&1 || true
echo "   $(sudo -u postgres psql -tAc 'select version();' 2>/dev/null | head -1)"

echo "== role + database =="
if grep -q '^VI_DATABASE_URL=' "$ETC_DIR/api.env" 2>/dev/null; then
  echo "   VI_DATABASE_URL already in api.env (kept, password unchanged)"
else
  PWD="$(openssl rand -hex 16)"
  if sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='vi_app'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER ROLE vi_app LOGIN PASSWORD '$PWD'" >/dev/null
  else
    sudo -u postgres psql -c "CREATE ROLE vi_app LOGIN PASSWORD '$PWD'" >/dev/null
  fi
  if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='value_investment'" | grep -q 1; then
    sudo -u postgres psql -c "CREATE DATABASE value_investment OWNER vi_app" >/dev/null
  fi
  echo "VI_DATABASE_URL=postgresql://vi_app:$PWD@127.0.0.1:5432/value_investment" >> "$ETC_DIR/api.env"
  chmod 600 "$ETC_DIR/api.env"
  echo "   created role vi_app + db value_investment; wrote VI_DATABASE_URL"
fi

echo "== nightly backup (pg_dump) =="
cp "$SRC/backup-db.sh" "$APP_DIR/backup-db.sh"
chmod +x "$APP_DIR/backup-db.sh"
# install a root cron at 03:10 daily (idempotent)
( crontab -l 2>/dev/null | grep -v 'value-investment-api/backup-db.sh' ; \
  echo "10 3 * * * /opt/value-investment-api/backup-db.sh >> /var/log/vi-db-backup.log 2>&1" ) | crontab -
echo "   cron installed (03:10 daily) → $BACKUP_DIR"

echo "== first backup (verify) =="
"$APP_DIR/backup-db.sh" && ls -lh "$BACKUP_DIR" | tail -2
echo "DONE"
