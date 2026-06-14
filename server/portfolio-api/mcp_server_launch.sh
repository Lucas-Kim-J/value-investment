#!/bin/sh
# Launch the capture MCP server (mcp_server.py) with the backend env + import path,
# so hermes can start it as a stdio MCP tool:
#   hermes -p app-<user> mcp add vi-capture --command /opt/value-investment-api/mcp_server_launch.sh
# Deployed to /opt/value-investment-api/ on the server (API venv is Python 3.13, which the `mcp` pkg needs).
cd /opt/value-investment-api
set -a; . /etc/value-investment/api.env; set +a
export PYTHONPATH=/opt/value-investment-api
exec /opt/value-investment-api/venv/bin/python /opt/value-investment-api/mcp_server.py
