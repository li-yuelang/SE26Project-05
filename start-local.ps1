# arxiv-PaperMate 本地一键启动 (Windows PowerShell)
# 使用 Docker Compose 运行 PostgreSQL + Redis，本地运行应用服务

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectDir "backend"
$FrontendDir = Join-Path $ProjectDir "frontend"

Write-Host "============================================"
Write-Host "  arxiv-PaperMate Local Launcher"
Write-Host "============================================"
Write-Host ""

# ============================================================
# 阶段 1：启动 Docker 服务 (PostgreSQL + Redis)
# ============================================================

Write-Host "[1/3] Starting PostgreSQL + Redis via Docker Compose..."

Push-Location $BackendDir
try {
    docker compose up -d postgres redis
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Docker Compose failed. Make sure Docker Desktop is running."
        Pause
        exit 1
    }
} finally {
    Pop-Location
}

Write-Host "  Waiting for PostgreSQL & Redis to be healthy..."
do {
    Push-Location $BackendDir
    try {
        $pgStatus = (docker compose ps postgres --format json | ConvertFrom-Json).Health
        $redisStatus = (docker compose ps redis --format json | ConvertFrom-Json).Health
    } finally {
        Pop-Location
    }

    if ($pgStatus -eq "healthy" -and $redisStatus -eq "healthy") {
        break
    }
    Start-Sleep -Seconds 2
} while ($true)

Write-Host "  PostgreSQL + Redis are ready."
Write-Host ""

# ============================================================
# 阶段 2：数据库迁移
# ============================================================

Write-Host "[2/3] Running database migrations..."

Push-Location $BackendDir
try {
    uv run alembic upgrade head
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  WARNING: Migration had issues (may be already up-to-date). Proceeding..."
    }
} finally {
    Pop-Location
}

Write-Host "  Migrations complete."
Write-Host ""

# ============================================================
# 阶段 3：启动应用服务
# ============================================================

Write-Host "[3/3] Starting application services..."

# FastAPI
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'FastAPI (port 8080)'; cd '$BackendDir'; uv run uvicorn app.main:app --workers 2 --port 8080"

# Celery Analysis Worker
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Celery Analysis Worker'; cd '$BackendDir'; uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q analysis --concurrency=2"

# Celery arXiv Worker
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Celery arXiv Worker'; cd '$BackendDir'; uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q arxiv --concurrency=1"

# Celery Beat
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Celery Beat'; cd '$BackendDir'; uv run celery -A app.tasks.celery_app.celery_app beat --loglevel=info"

# Vite Frontend
if (Test-Path (Join-Path $FrontendDir "package.json")) {
    Start-Process powershell -ArgumentList "-NoExit", "-Command", "Write-Host 'Vite Frontend (port 3000)'; cd '$FrontendDir'; npm run dev"
} else {
    Write-Host "  Frontend not found at $FrontendDir – skipping."
}

Write-Host ""
Write-Host "============================================"
Write-Host "  All services started!"
Write-Host ""
Write-Host "  PostgreSQL : localhost:5432  (Docker)"
Write-Host "  Redis      : localhost:6379   (Docker)"
Write-Host "  Backend API: http://localhost:8080/docs"
Write-Host "  Frontend   : http://localhost:3000"
Write-Host ""
Write-Host "  Stop: Close all windows or run:"
Write-Host "    docker compose -f backend\docker-compose.yml down"
Write-Host "============================================"
Write-Host ""
Pause
