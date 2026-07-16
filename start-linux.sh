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
    echo "错误: 未检测到可用的终端模拟器，请安装 gnome-terminal / konsole / xterm 等。"
    exit 1
fi

echo "============================================"
echo "  arxiv-PaperMate 一键启动 (Linux)"
echo "  终端: $TERMINAL"
echo "============================================"
echo ""

open_terminal() {
    local title="$1"
    local cmd="$2"
    shift 2

    case "$TERMINAL" in
        gnome-terminal)
            gnome-terminal --title="$title" -- bash -c "$cmd; exec bash" &
            ;;
        konsole)
            konsole --new-tab -p tabtitle="$title" -e bash -c "$cmd; exec bash" &
            ;;
        xfce4-terminal)
            xfce4-terminal --title="$title" --command="bash -c '$cmd; exec bash'" &
            ;;
        lxterminal)
            lxterminal --title="$title" --command="bash -c '$cmd; exec bash'" &
            ;;
        xterm)
            xterm -title "$title" -e bash -c "$cmd; exec bash" &
            ;;
    esac
}

# ---- 1. PostgreSQL SSH 端口映射 ----
echo "[1/5] 启动 PostgreSQL SSH 隧道..."
open_terminal "PostgreSQL SSH Tunnel" "echo 'PostgreSQL SSH Tunnel'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37"

# ---- 2. Redis SSH 端口映射 ----
echo "[2/5] 启动 Redis SSH 隧道..."
open_terminal "Redis SSH Tunnel" "echo 'Redis SSH Tunnel'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37"

# ---- 3. FastAPI 后端 ----
echo "[3/5] 启动 FastAPI 后端 (端口 8080)..."
open_terminal "FastAPI Backend" "echo 'FastAPI Backend'; cd '$PROJECT_DIR/backend' && uv run uvicorn app.main:app --reload --port 8080"

# ---- 4. Celery Worker ----
echo "[4/5] 启动 Celery Worker..."
open_terminal "Celery Worker" "echo 'Celery Worker'; cd '$PROJECT_DIR/backend' && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo"

# ---- 5. 前端 Vite ----
echo "[5/5] 启动前端开发服务器 (端口 3000)..."
open_terminal "Frontend Vite" "echo 'Frontend Vite'; cd '$PROJECT_DIR/frontend' && npm run dev"

echo ""
echo "============================================"
echo "  所有服务已启动！请等待各窗口就绪后访问："
echo "  后端 API 文档 : http://localhost:8080/docs"
echo "  前端页面      : http://localhost:3000"
echo "============================================"
