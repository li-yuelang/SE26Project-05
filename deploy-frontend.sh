#!/usr/bin/env bash
# ============================================================
# PaperMate 前端部署脚本
# 用法: chmod +x deploy-frontend.sh && ./deploy-frontend.sh
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "[1/3] Building frontend..."
cd "${SCRIPT_DIR}/frontend"
npm ci
npm run build

echo "[2/3] Deploying static files..."
sudo mkdir -p /var/www/papermate/frontend
sudo cp -r dist/* /var/www/papermate/frontend/

echo "[3/3] Configuring Nginx..."
sudo cp "${SCRIPT_DIR}/nginx.conf" /etc/nginx/conf.d/papermate.conf

echo ""
echo "============================================"
echo "  前端部署完成！"
echo "  检查 Nginx 配置: sudo nginx -t"
echo "  重载 Nginx:      sudo nginx -s reload"
echo "  访问:            http://<公网IP>"
echo "============================================"
