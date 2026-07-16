@echo off
chcp 65001 >nul
title arxiv-PaperMate Launcher

echo ============================================
echo   arxiv-PaperMate 一键启动 (Windows)
echo ============================================
echo.

set "PROJECT_DIR=%~dp0"

:: ---- 1. PostgreSQL SSH 端口映射 ----
echo [1/5] 启动 PostgreSQL SSH 隧道...
start "PostgreSQL SSH Tunnel" cmd /k "ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37"

:: ---- 2. Redis SSH 端口映射 ----
echo [2/5] 启动 Redis SSH 隧道...
start "Redis SSH Tunnel" cmd /k "ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37"

:: ---- 3. FastAPI 后端 ----
echo [3/5] 启动 FastAPI 后端 (端口 8080)...
start "FastAPI Backend" cmd /k "cd /d %PROJECT_DIR%backend && uv run uvicorn app.main:app --reload --port 8080"

:: ---- 4. Celery Worker ----
echo [4/5] 启动 Celery Worker...
start "Celery Worker" cmd /k "cd /d %PROJECT_DIR%backend && uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo"

:: ---- 5. 前端 Vite ----
echo [5/5] 启动前端开发服务器 (端口 3000)...
start "Frontend Vite" cmd /k "cd /d %PROJECT_DIR%frontend && npm run dev"

echo.
echo ============================================
echo   所有服务已启动！请等待各窗口就绪后访问：
echo   后端 API 文档 : http://localhost:8080/docs
echo   前端页面      : http://localhost:3000
echo ============================================
echo.
pause
