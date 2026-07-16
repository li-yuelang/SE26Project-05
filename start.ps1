# arxiv-PaperMate 一键启动 (Windows PowerShell)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================"
Write-Host "  arxiv-PaperMate 一键启动 (Windows)"
Write-Host "============================================"
Write-Host ""

# ---- 1. PostgreSQL SSH 隧道 ----
Write-Host "[1/5] 启动 PostgreSQL SSH 隧道..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'PostgreSQL SSH Tunnel'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37"

# ---- 2. Redis SSH 隧道 ----
Write-Host "[2/5] 启动 Redis SSH 隧道..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Redis SSH Tunnel'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37"

# ---- 3. FastAPI 后端 ----
Write-Host "[3/5] 启动 FastAPI 后端 (端口 8080)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'FastAPI Backend'; cd '$ProjectDir\backend'; uv run uvicorn app.main:app --reload --port 8080"

# ---- 4. Celery Worker ----
Write-Host "[4/5] 启动 Celery Worker..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Celery Worker'; cd '$ProjectDir\backend'; uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo"

# ---- 5. 前端 Vite ----
Write-Host "[5/5] 启动前端开发服务器 (端口 3000)..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Frontend Vite'; cd '$ProjectDir\frontend'; npm run dev"

Write-Host ""
Write-Host "============================================"
Write-Host "  所有服务已启动！请等待各窗口就绪后访问："
Write-Host "  后端 API 文档 : http://localhost:8080/docs"
Write-Host "  前端页面      : http://localhost:3000"
Write-Host "============================================"
Write-Host ""
Pause
