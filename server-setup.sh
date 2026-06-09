#!/usr/bin/env bash
#
# server-setup.sh — 服务器初始化脚本（幂等）
#
# 作用：在一台全新的 Ubuntu/Debian 服务器上安装并配置 nginx，
# 让它作为 value-investment 静态站点的 web server。
#
# 该脚本是幂等的：重复运行是安全的，可作为「可复现的服务器配置文档」。
# 你可能已经手动跑过其中的步骤，再跑一遍也不会出问题。
#
# 在服务器上以 root 运行。推荐从本地通过 SSH 别名一键执行：
#   ssh openclaw 'bash -s' < server-setup.sh
#
# 注意：本文件会进入公开仓库，不包含任何具体 IP / 端口 / 用户名。

set -euo pipefail

WEB_ROOT="/var/www/value-investment"
SITE_NAME="value-investment"
SITE_AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
SITE_ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"

echo "🔧 [1/6] 安装 nginx ..."
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y nginx

echo "📁 [2/6] 创建 web root: ${WEB_ROOT} ..."
mkdir -p "${WEB_ROOT}"

echo "📝 [3/6] 写入 nginx vhost 配置 ..."
cat > "${SITE_AVAILABLE}" <<EOF
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    root ${WEB_ROOT};
    index dashboard.html index.html;

    server_name _;

    location / {
        try_files \$uri \$uri/ =404;
    }
}
EOF

echo "🔗 [4/6] 启用站点并移除默认站点 ..."
ln -sf "${SITE_AVAILABLE}" "${SITE_ENABLED}"
rm -f /etc/nginx/sites-enabled/default

echo "✅ [5/6] 测试并重启 nginx ..."
nginx -t
systemctl enable nginx
systemctl restart nginx

echo "🛡️  [6/6] 如果 ufw 已启用，则放行 80 端口 ..."
if command -v ufw >/dev/null 2>&1 && ufw status | grep -q "Status: active"; then
  ufw allow 80/tcp
  echo "✅ 已在 ufw 中放行 80 端口。"
else
  echo "ℹ️  ufw 未启用或未安装，跳过防火墙配置。"
fi

echo "🎉 服务器初始化完成！nginx 已在 80 端口提供 ${WEB_ROOT} 的静态站点。"
echo "ℹ️  提醒：如果是云服务器，记得在云控制台的安全组里放行 80 端口。"
