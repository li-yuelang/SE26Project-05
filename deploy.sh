#!/usr/bin/env bash
# ============================================================
# PaperMate 云端部署脚本（host 网络模式）
# PG 和 Redis 已在宿主机 Docker 中运行，API/Worker 通过
# --network host 直接使用 127.0.0.1 连接它们。
#
# ⚠️ 首次部署前：
#    1. 填写 backend/.env.production 中所有 <填写...> 占位符
#    2. 确保 8080 端口未被占用
# ============================================================
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/backend/.env.production"

if [ ! -f "${ENV_FILE}" ]; then
  echo "错误: 找不到 ${ENV_FILE}"
  echo "请先填写 backend/.env.production（模板: backend/.env.production.example）"
  exit 1
fi

echo "============================================"
echo "  PaperMate Cloud Deploy (host network)"
echo "  依赖: PG=127.0.0.1:5432  Redis=127.0.0.1:6379"
echo "============================================"

# ---- 1. 验证 PG 可达 ----
echo "[1/3] Verifying PostgreSQL is reachable..."
if ! docker exec papermate-postgres pg_isready -U papermate -d papermate >/dev/null 2>&1; then
  echo "错误: PostgreSQL 容器 (papermate-postgres) 未就绪"
  exit 1
fi
echo "  PostgreSQL OK"

# ---- 2. 构建镜像 & 数据库迁移 ----
echo "[2/3] Building API image & running migrations..."
docker build -t papermate-api:latest "${SCRIPT_DIR}/backend"
docker run --rm \
  --name papermate-migrate \
  --network host \
  --env-file "${ENV_FILE}" \
  papermate-api:latest \
  alembic upgrade head

# ---- 3. 启动所有服务 ----
echo "[3/3] Starting API + Celery workers..."

# API (FastAPI) → host 端口 8080
docker run -d \
  --name papermate-api \
  --network host \
  --env-file "${ENV_FILE}" \
  --restart unless-stopped \
  papermate-api:latest \
  uvicorn app.main:app --host 127.0.0.1 --port 8080

# Celery analysis worker
docker run -d \
  --name papermate-worker-analysis \
  --network host \
  --env-file "${ENV_FILE}" \
  --restart unless-stopped \
  papermate-api:latest \
  celery -A app.tasks.celery_app.celery_app worker --loglevel=info -Q analysis --concurrency=2

# Celery arxiv worker
docker run -d \
  --name papermate-worker-arxiv \
  --network host \
  --env-file "${ENV_FILE}" \
  --restart unless-stopped \
  papermate-api:latest \
  celery -A app.tasks.celery_app.celery_app worker --loglevel=info -Q arxiv --concurrency=1

# Celery beat
docker run -d \
  --name papermate-beat \
  --network host \
  --env-file "${ENV_FILE}" \
  --restart unless-stopped \
  papermate-api:latest \
  celery -A app.tasks.celery_app.celery_app beat --loglevel=info

echo ""
echo "============================================"
echo "  部署完成！"
echo "  API: http://<公网IP>:8080/health"
echo "  Nginx 前端: 执行 deploy-frontend.sh"
echo "============================================"
