#!/usr/bin/env bash
#
# deploy.sh — 本地一键部署脚本
#
# 流程：构建静态站点 (python3 build.py) → rsync 同步 dist/ 到服务器 web root。
# 服务器通过本地 SSH 别名 `openclaw` 访问（别名在 ~/.ssh/config 里配置，
# 不在本脚本中暴露任何 IP / 端口 / 用户名）。
#
# 用法：
#   chmod +x deploy.sh
#   ./deploy.sh

set -euo pipefail

REMOTE="openclaw:/var/www/value-investment/"

echo "🚀 开始部署 value-investment ..."

# 1. 检查依赖
echo "🔍 [1/3] 检查本地依赖 (python3, rsync) ..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ 未找到 python3，请先安装 Python 3。"
  exit 1
fi
if ! command -v rsync >/dev/null 2>&1; then
  echo "❌ 未找到 rsync，请先安装 rsync。"
  exit 1
fi
echo "✅ 依赖检查通过。"

# 2. 构建静态站点
echo "🛠️  [2/3] 构建静态站点 (python3 build.py) ..."
python3 build.py
echo "✅ 构建完成，产物在 dist/ 。"

# 3. 同步到服务器
echo "📡 [3/3] 同步 dist/ 到服务器 (${REMOTE}) ..."
rsync -avz --delete -e "ssh" dist/ "${REMOTE}"
echo "✅ 同步完成。"

echo "🎉 部署成功！静态站点已更新到服务器。"
