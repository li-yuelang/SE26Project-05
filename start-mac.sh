#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  arxiv-PaperMate 一键启动 (macOS)"
echo "============================================"
echo ""

# ---- 1. PostgreSQL SSH 端口映射 ----
echo "[1/5] 启动 PostgreSQL SSH 隧道..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'PostgreSQL SSH Tunnel'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37\"
end tell"

# ---- 2. Redis SSH 端口映射 ----
echo "[2/5] 启动 Redis SSH 隧道..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Redis SSH Tunnel'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37\"
end tell"

# ---- 3. FastAPI 后端 ----
echo "[3/5] 启动 FastAPI 后端 (端口 8080)..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'FastAPI Backend'; cd '$PROJECT_DIR/backend' && uv run uvicorn app.main:app --reload --port 8080\"
end tell"

# ---- 4. Celery Worker ----
echo "[4/5] 启动 Celery Worker..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Celery Worker'; cd '$PROJECT_DIR/backend' && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo\"
end tell"

# ---- 5. 前端 Vite ----
echo "[5/5] 启动前端开发服务器 (端口 3000)..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Frontend Vite'; cd '$PROJECT_DIR/frontend' && npm run dev\"
end tell"

echo ""
echo "============================================"
echo "  所有服务已启动！请等待各窗口就绪后访问："
echo "  后端 API 文档 : http://localhost:8080/docs"
echo "  前端页面      : http://localhost:3000"
echo "============================================"
