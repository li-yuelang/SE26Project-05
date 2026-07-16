#!/bin/bash

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 检测可用的终端模拟器
detect_terminal() {
    if command -v gnome-terminal &>/dev/null; then
        echo "gnome-terminal"
    elif command -v konsole &>/dev/null; then
        echo "konsole"
    elif command -v xfce4-terminal &>/dev/null; then
        echo "xfce4-terminal"
    elif command -v lxterminal &>/dev/null; then
        echo "lxterminal"
    elif command -v xterm &>/dev/null; then
        echo "xterm"
    else
        echo "none"
    fi
}

TERMINAL=$(detect_terminal)

if [ "$TERMINAL" = "none" ]; then
    echo "Error: No terminal emulator found. Install gnome-terminal / konsole / xterm etc."
    exit 1
fi

echo "============================================"
echo "  arxiv-PaperMate Launcher (Linux)"
echo "  Terminal: $TERMINAL"
echo "============================================"
echo ""

open_terminal() {
    local title="$1"
    local cmd="$2"

    case "$TERMINAL" in
        gnome-terminal)
            gnome-terminal --title="$title" -- bash -c "$cmd; exec bash" &
            ;;
        konsole)
            konsole --new-tab -p tabtitle="$title" -e bash -c "$cmd; exec bash" &
            ;;
        xfce4-terminal)
            xfce4-terminal --title="$title" -e "bash -c \"$cmd; exec bash\"" &
            ;;
        lxterminal)
            lxterminal --title="$title" -e "bash -c \"$cmd; exec bash\"" &
            ;;
        xterm)
            xterm -title "$title" -e "bash -c \"$cmd; exec bash\"" &
            ;;
    esac
}

# ---- 1. PostgreSQL SSH 隧道 ----
echo "[1/5] Starting PostgreSQL SSH tunnel..."
open_terminal "PostgreSQL SSH Tunnel" "echo 'PostgreSQL Tunnel'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37"

# ---- 2. Redis SSH 隧道 ----
echo "[2/5] Starting Redis SSH tunnel..."
open_terminal "Redis SSH Tunnel" "echo 'Redis Tunnel'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37"

# ---- 3. FastAPI 后端 ----
echo "[3/5] Starting FastAPI (port 8080)..."
open_terminal "FastAPI Backend" "echo 'FastAPI'; cd \"$PROJECT_DIR/backend\" && uv run uvicorn app.main:app --reload --port 8080"

# ---- 4. Celery Worker ----
echo "[4/5] Starting Celery Worker..."
open_terminal "Celery Worker" "echo 'Celery Worker'; cd \"$PROJECT_DIR/backend\" && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo"

# ---- 5. 前端 Vite ----
echo "[5/5] Starting Frontend (port 3000)..."
open_terminal "Frontend Vite" "echo 'Vite Frontend'; cd \"$PROJECT_DIR/frontend\" && npm run dev"

echo ""
echo "============================================"
echo "  All services started!"
echo "  Backend API: http://localhost:8080/docs"
echo "  Frontend   : http://localhost:3000"
echo "============================================"
