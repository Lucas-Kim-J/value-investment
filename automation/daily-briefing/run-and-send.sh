#!/usr/bin/env bash
# Build the daily briefing and deliver it to Feishu via hermes.
#
# Run this ON THE SERVER (where hermes is installed). Schedule it with either:
#
#   • hermes cron (hermes-native):
#       hermes cron create --name daily-briefing --schedule "25 7 * * *" \
#         --command "/path/to/run-and-send.sh"
#
#   • system cron (crontab -e), 07:25 北京时间（按机器时区调整 UTC 偏移）:
#       25 7 * * *  /path/to/run-and-send.sh >> /var/log/daily-briefing.log 2>&1
#
# Override the target with BRIEFING_TARGET (default: config feishu_target / 'feishu').
set -euo pipefail
cd "$(dirname "$0")"
exec python3 briefing.py ${BRIEFING_TARGET:+--to "$BRIEFING_TARGET"}
