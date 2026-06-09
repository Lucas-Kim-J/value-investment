#!/usr/bin/env bash
# Nightly PostgreSQL backup for the input portal. Installed to /opt by setup-db.sh,
# run by cron. Keeps the newest 30 gzipped dumps.
set -euo pipefail

BACKUP_DIR=/var/backups/value-investment
mkdir -p "$BACKUP_DIR"

# VI_DATABASE_URL lives in api.env (server-only)
# shellcheck disable=SC1091
source /etc/value-investment/api.env

TS="$(date -u +%Y%m%d-%H%M%S)"
OUT="$BACKUP_DIR/vi-$TS.sql.gz"
pg_dump "$VI_DATABASE_URL" | gzip > "$OUT"

# prune: keep newest 30
ls -1t "$BACKUP_DIR"/vi-*.sql.gz 2>/dev/null | tail -n +31 | xargs -r rm -f
echo "$(date -u +%FT%TZ) backup ok: $OUT ($(du -h "$OUT" | cut -f1))"
