# arxiv-PaperMate 一键启动 (Windows PowerShell)

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "============================================"
Write-Host "  arxiv-PaperMate Launcher (Windows)"
Write-Host "============================================"
Write-Host ""

# ============================================================
# 阶段 1：启动 SSH 隧道
# ============================================================

Write-Host "[1/2] Starting SSH tunnels..."
Write-Host "  Please enter SSH passwords in the popup windows."
Write-Host ""

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'PostgreSQL Tunnel (port 15432)'; ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Redis Tunnel (port 6379)'; ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37"

Write-Host "  Waiting 30s for SSH tunnels to be established..."
Start-Sleep -Seconds 30
Write-Host ""

# ============================================================
# 阶段 2：启动应用服务
# ============================================================

Write-Host "[2/2] Starting application services..."

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'FastAPI (port 8080)'; cd '$ProjectDir\backend'; uv run uvicorn app.main:app --reload --port 8080"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Celery Worker'; cd '$ProjectDir\backend'; uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Vite Frontend (port 3000)'; cd '$ProjectDir\frontend'; npm run dev"

Write-Host ""
Write-Host "============================================"
Write-Host "  All services started!"
Write-Host "  Backend API: http://localhost:8080/docs"
Write-Host "  Frontend   : http://localhost:3000"
Write-Host "============================================"
Write-Host ""
Pause
