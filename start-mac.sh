#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  arxiv-PaperMate Launcher (macOS)"
echo "============================================"
echo ""

# ============================================================
# 阶段 1：启动 SSH 隧道
# ============================================================

echo "[1/2] Starting SSH tunnels..."
echo "Please enter SSH passwords in the popup Terminal windows."
echo ""

osascript -e "tell app \"Terminal\"
    do script \"echo 'PostgreSQL Tunnel (port 15432)'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37\"
end tell"

osascript -e "tell app \"Terminal\"
    do script \"echo 'Redis Tunnel (port 6379)'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37\"
end tell"

echo "Waiting 30s for SSH tunnels to be established..."
sleep 30
echo ""

# ============================================================
# 阶段 2：启动应用服务
# ============================================================

echo "[2/2] Starting application services..."

osascript -e "tell app \"Terminal\"
    do script \"echo 'FastAPI (port 8080)'; cd '$PROJECT_DIR/backend' && uv run uvicorn app.main:app --reload --port 8080\"
end tell"

osascript -e "tell app \"Terminal\"
    do script \"echo 'Celery Default Worker'; cd '$PROJECT_DIR/backend' && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q default\"
end tell"

osascript -e "tell app \"Terminal\"
    do script \"echo 'Celery arXiv Worker'; cd '$PROJECT_DIR/backend' && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q arxiv --concurrency=1\"
end tell"

osascript -e "tell app \"Terminal\"
    do script \"echo 'Vite Frontend (port 3000)'; cd '$PROJECT_DIR/frontend' && npm run dev\"
end tell"

echo ""
echo "============================================"
echo "  All services started!"
echo "  Backend API: http://localhost:8080/docs"
echo "  Frontend   : http://localhost:3000"
echo "============================================"
