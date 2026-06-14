#!/usr/bin/env bash
# Run the content signal pipeline once and deliver to Feishu via hermes.
#
# Run ON THE SERVER (hermes + PostgreSQL + faster-whisper installed). Schedule:
#
#   • system cron (crontab -e) — 08:00 北京时间.
#     If the server clock is UTC, that is 00:00 UTC:
#       0 0 * * *  /path/to/run.sh >> /var/log/content-pipeline.log 2>&1
#     If TZ=Asia/Shanghai:
#       0 8 * * *  /path/to/run.sh >> /var/log/content-pipeline.log 2>&1
#
#   • or hermes cron:
#       hermes cron create --name content-pipeline --schedule "0 0 * * *" \
#         --command "/path/to/run.sh"
set -euo pipefail
cd "$(dirname "$0")/.."          # server/portfolio-api (pythonpath root)
exec python3 -m content_pipeline.run "$@"
