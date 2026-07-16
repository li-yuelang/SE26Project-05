#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================"
echo "  arxiv-PaperMate Launcher (macOS)"
echo "============================================"
echo ""

# ---- 1. PostgreSQL SSH 隧道 ----
echo "[1/5] Starting PostgreSQL SSH tunnel..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'PostgreSQL Tunnel'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37\"
end tell"

# ---- 2. Redis SSH 隧道 ----
echo "[2/5] Starting Redis SSH tunnel..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Redis Tunnel'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37\"
end tell"

# ---- 3. FastAPI 后端 ----
echo "[3/5] Starting FastAPI (port 8080)..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'FastAPI'; cd '$PROJECT_DIR/backend' && uv run uvicorn app.main:app --reload --port 8080\"
end tell"

# ---- 4. Celery Worker ----
echo "[4/5] Starting Celery Worker..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Celery Worker'; cd '$PROJECT_DIR/backend' && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo\"
end tell"

# ---- 5. 前端 Vite ----
echo "[5/5] Starting Frontend (port 3000)..."
osascript -e "tell app \"Terminal\"
    do script \"echo 'Vite Frontend'; cd '$PROJECT_DIR/frontend' && npm run dev\"
end tell"

echo ""
echo "============================================"
echo "  All services started!"
echo "  Backend API: http://localhost:8080/docs"
echo "  Frontend   : http://localhost:3000"
echo "============================================"
