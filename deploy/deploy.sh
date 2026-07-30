#!/usr/bin/env bash
# ============================================================
# PaperMate 云端部署脚本
# 
# 使用说明:
#   1. 将项目代码传输到云服务器
#   2. 复制 deploy/.env.production 到项目根目录并填写变量
#   3. 运行: bash deploy/deploy.sh
# ============================================================

set -euo pipefail

# ---- 配置 ----
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env.production"

# 容器名称
API_CONTAINER="papermate-api"
WORKER_ANALYSIS_CONTAINER="papermate-worker-analysis"
WORKER_ARXIV_CONTAINER="papermate-worker-arxiv"
BEAT_CONTAINER="papermate-beat"
NGINX_CONTAINER="papermate-nginx"
MIGRATE_CONTAINER="papermate-migrate"

# 镜像名称
BACKEND_IMAGE="papermate-backend:latest"
NGINX_IMAGE="papermate-nginx:latest"

# ---- 颜色输出 ----
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

log_info()  { echo -e "${GREEN}[INFO]${NC}  $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC}  $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step()  { echo -e "${BLUE}[STEP]${NC}  $1"; }

# ---- 检查前置条件 ----
check_prerequisites() {
    log_step "检查前置条件..."

    if ! command -v docker &>/dev/null; then
        log_error "Docker 未安装，请先安装 Docker"
        exit 1
    fi
    log_info "Docker 已安装: $(docker --version)"

    if ! docker info &>/dev/null; then
        log_error "Docker 未运行或无权限，请启动 Docker 并确保当前用户在 docker 组中"
        exit 1
    fi

    if [ ! -f "$ENV_FILE" ]; then
        log_error "环境变量文件不存在: ${ENV_FILE}"
        log_info "请先复制并配置: cp deploy/.env.production .env.production"
        log_info "然后编辑 .env.production 填写你的配置变量"
        exit 1
    fi
    log_info "环境变量文件: ${ENV_FILE}"

    # 检查 .env.production 中是否还有未填写的占位符
    if grep -q '<REPLACE_' "$ENV_FILE" 2>/dev/null; then
        log_warn "检测到未填写的占位符变量 (标记为 <REPLACE_...)，请先编辑 ${ENV_FILE}"
        log_warn "未填写的变量:"
        grep '<REPLACE_' "$ENV_FILE" | sed 's/^/    /'
        echo ""
        read -rp "是否继续部署? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ---- 加载环境变量 ----
load_env() {
    log_step "加载环境变量..."
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
    log_info "环境变量已加载"
    log_info "  数据库: ${DATABASE_URL}"
    log_info "  Redis:  ${REDIS_URL}"
}

# ---- 检查 PostgreSQL pgvector 扩展 ----
check_pgvector() {
    log_step "检查 PostgreSQL pgvector 扩展..."

    # 从 DATABASE_URL 中提取连接参数
    # 格式: postgresql+asyncpg://user:password@host:port/dbname
    local db_url="${DATABASE_URL}"
    db_url="${db_url#postgresql+asyncpg://}"
    local db_user="${db_url%%:*}"
    db_url="${db_url#*:}"
    local db_pass="${db_url%%@*}"
    db_url="${db_url#*@}"
    local db_host="${db_url%%:*}"
    db_url="${db_url#*:}"
    local db_port="${db_url%%/*}"
    local db_name="${db_url##*/}"

    log_info "检查 pgvector 扩展 (${db_host}:${db_port}/${db_name})..."

    # 使用 Docker 运行 psql 检查
    if docker run --rm --network host \
        -e PGPASSWORD="$db_pass" \
        postgres:16-alpine \
        psql -h "$db_host" -p "$db_port" -U "$db_user" -d "$db_name" \
        -c "SELECT * FROM pg_available_extensions WHERE name = 'vector';" 2>/dev/null | grep -q vector; then
        log_info "pgvector 扩展可用"
    else
        log_warn "============================================="
        log_warn "pgvector 扩展不可用！"
        log_warn ""
        log_warn "PaperMate 需要 pgvector 扩展来支持语义搜索功能。"
        log_warn "你的云端 PostgreSQL 可能版本较旧或未安装此扩展。"
        log_warn ""
        log_warn "解决方案（选其一）:"
        log_warn "  1. 在现有 PostgreSQL 中安装 pgvector:"
        log_warn "     https://github.com/pgvector/pgvector#installation"
        log_warn ""
        log_warn "  2. 若无法在原数据库安装，可额外启动带 pgvector 的 PostgreSQL:"
        log_warn "     docker run -d --name papermate-pg --network host \\"
        log_warn "       -e POSTGRES_DB=papermate -e POSTGRES_USER=papermate \\"
        log_warn "       -e POSTGRES_PASSWORD=<密码> \\"
        log_warn "       -v papermate_pg_data:/var/lib/postgresql/data \\"
        log_warn "       pgvector/pgvector:pg16"
        log_warn ""
        log_warn "  3. 继续部署（不保证正常运行）"
        log_warn "============================================="
        read -rp "是否继续? (y/N): " confirm
        if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
            exit 1
        fi
    fi
}

# ---- 构建 Docker 镜像 ----
build_images() {
    log_step "构建 Docker 镜像..."

    cd "$PROJECT_DIR"

    log_info "构建后端镜像..."
    docker build -t "$BACKEND_IMAGE" -f backend/Dockerfile backend/

    log_info "构建前端 + Nginx 镜像..."
    docker build -t "$NGINX_IMAGE" -f deploy/Dockerfile.nginx .

    log_info "镜像构建完成"
}

# ---- 停止旧容器 ----
stop_old_containers() {
    log_step "停止旧容器..."

    for container in "$API_CONTAINER" "$WORKER_ANALYSIS_CONTAINER" "$WORKER_ARXIV_CONTAINER" "$BEAT_CONTAINER" "$NGINX_CONTAINER"; do
        if docker ps -a --format '{{.Names}}' | grep -q "^${container}$"; then
            log_info "停止并删除: ${container}"
            docker stop "$container" 2>/dev/null || true
            docker rm "$container" 2>/dev/null || true
        fi
    done
}

# ---- 数据库迁移 ----
run_migration() {
    log_step "运行数据库迁移 (Alembic)..."

    # 用临时容器运行迁移
    docker run --rm --network host \
        --env-file "$ENV_FILE" \
        --name "$MIGRATE_CONTAINER" \
        "$BACKEND_IMAGE" \
        alembic upgrade head

    log_info "数据库迁移完成"
}

# ---- 启动服务 ----
start_services() {
    log_step "启动服务..."

    # 后端 API (8080 端口)
    log_info "启动后端 API 服务..."
    docker run -d --network host \
        --name "$API_CONTAINER" \
        --restart unless-stopped \
        --env-file "$ENV_FILE" \
        "$BACKEND_IMAGE" \
        uvicorn app.main:app --host 0.0.0.0 --port 8080

    # Celery Worker - 论文分析队列
    log_info "启动 Celery Worker (analysis)..."
    docker run -d --network host \
        --name "$WORKER_ANALYSIS_CONTAINER" \
        --restart unless-stopped \
        --env-file "$ENV_FILE" \
        "$BACKEND_IMAGE" \
        celery -A app.tasks.celery_app.celery_app worker --loglevel=info -Q analysis --concurrency=2

    # Celery Worker - arXiv 抓取队列
    log_info "启动 Celery Worker (arxiv)..."
    docker run -d --network host \
        --name "$WORKER_ARXIV_CONTAINER" \
        --restart unless-stopped \
        --env-file "$ENV_FILE" \
        "$BACKEND_IMAGE" \
        celery -A app.tasks.celery_app.celery_app worker --loglevel=info -Q arxiv --concurrency=1

    # Celery Beat - 定时任务调度
    log_info "启动 Celery Beat..."
    docker run -d --network host \
        --name "$BEAT_CONTAINER" \
        --restart unless-stopped \
        --env-file "$ENV_FILE" \
        "$BACKEND_IMAGE" \
        celery -A app.tasks.celery_app.celery_app beat --loglevel=info

    # Nginx (前端 + 反向代理, 80 端口)
    log_info "启动 Nginx 服务..."
    docker run -d --network host \
        --name "$NGINX_CONTAINER" \
        --restart unless-stopped \
        "$NGINX_IMAGE"
}

# ---- 健康检查 ----
health_check() {
    log_step "健康检查..."
    sleep 3

    # 检查所有容器状态
    local all_healthy=true
    for container in "$API_CONTAINER" "$WORKER_ANALYSIS_CONTAINER" "$WORKER_ARXIV_CONTAINER" "$BEAT_CONTAINER" "$NGINX_CONTAINER"; do
        if docker ps --format '{{.Names}}' | grep -q "^${container}$"; then
            log_info "  ${container}: 运行中"
        else
            log_error "  ${container}: 未运行"
            all_healthy=false
        fi
    done

    # 检查 API 健康
    if curl -sf http://127.0.0.1:8080/health > /dev/null 2>&1; then
        log_info "  API 健康检查: OK (http://127.0.0.1:8080/health)"
    else
        log_warn "  API 健康检查: 无法访问，请检查日志"
        all_healthy=false
    fi

    if $all_healthy; then
        echo ""
        log_info "============================================"
        log_info "  部署成功！"
        log_info "  访问地址: http://<浮动IP>"
        log_info "  API 文档: http://<浮动IP>:8080/docs"
        log_info "============================================"
    else
        log_warn "部分服务可能未正常启动，请检查日志:"
        log_warn "  docker logs ${API_CONTAINER}"
        log_warn "  docker logs ${WORKER_ANALYSIS_CONTAINER}"
        log_warn "  docker logs ${NGINX_CONTAINER}"
    fi
}

# ---- 查看日志 ----
show_logs() {
    echo ""
    log_info "查看各服务日志:"
    echo "  docker logs -f ${API_CONTAINER}"
    echo "  docker logs -f ${WORKER_ANALYSIS_CONTAINER}"
    echo "  docker logs -f ${WORKER_ARXIV_CONTAINER}"
    echo "  docker logs -f ${BEAT_CONTAINER}"
    echo "  docker logs -f ${NGINX_CONTAINER}"
    echo ""
    log_info "查看所有容器状态:"
    echo "  docker ps --filter 'name=papermate'"
}

# ---- 主流程 ----
main() {
    echo ""
    echo "========================================"
    echo "  PaperMate 云端部署脚本"
    echo "========================================"
    echo ""

    check_prerequisites
    load_env
    check_pgvector
    build_images
    stop_old_containers
    run_migration
    start_services
    health_check
    show_logs
}

main "$@"
