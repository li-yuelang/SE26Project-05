# arxiv-PaperMate

AI-powered ArXiv paper reader with intelligent summaries, note-taking, and knowledge management.

## 项目结构

```text
/opt/papermate/
├── frontend/               React 前端（Vite + Ant Design）
├── backend/                FastAPI 后端（Python）
├── deploy.sh               部署脚本（后端容器）
├── deploy-frontend.sh      部署脚本（前端 + Nginx）
├── stop.sh                 停止 API/Worker 容器
└── nginx.conf              Nginx 反向代理配置
```

## 架构

```text
                    ┌──────────────────────────────────┐
                    │        Nginx (port 80)            │
                    │  /         → 前端静态文件          │
                    │  /api/*    → proxy 127.0.0.1:8080 │
                    └──────────────┬───────────────────┘
                                   │
    ┌──────────────────────────────┼──────────────────────────────┐
    │                    宿主机 (Host Network)                      │
    │                                                              │
    │  ┌──────────────────────────────────────┐                    │
    │  │   papermate-api              :8080   │  ← uvicorn (host) │
    │  │   papermate-worker-analysis          │  ← Celery analysis│
    │  │   papermate-worker-arxiv             │  ← Celery arxiv   │
    │  │   papermate-beat                     │  ← Celery beat    │
    │  └──────────────────────────────────────┘                    │
    │           │                  │                               │
    │           ▼                  ▼                               │
    │  ┌──────────────┐   ┌──────────────┐                        │
    │  │ PostgreSQL   │   │    Redis     │                        │
    │  │ :5432 (host) │   │  :6379 (host)│                        │
    │  └──────────────┘   └──────────────┘                        │
    └──────────────────────────────────────────────────────────────┘
```

API / Worker 容器通过 `--network host` 直连宿主机已有的 PostgreSQL 和 Redis，前端通过 Nginx 统一对外提供服务。

## 云端要求

| 依赖 | 说明 |
|------|------|
| Docker | 已安装（不需要 docker-compose） |
| PostgreSQL + pgvector | 已运行，容器名 `papermate-postgres`，监听 `127.0.0.1:5432` |
| Redis | 已运行，容器名 `redis`，监听 `0.0.0.0:6379` |
| Nginx | 已安装 |
| 端口 | 80（Nginx）、8080（API，仅 localhost） |
| 防火墙/安全组 | 放行 80（HTTP）和 443（HTTPS）端口 |

## 部署

### 1. 填写配置

部署前需要编辑两个配置文件中的 `<...>` 占位符：

**`backend/.env.production`** — 6 处：

```env
DATABASE_URL=postgresql+asyncpg://papermate:<数据库密码>@127.0.0.1:5432/papermate
JWT_SECRET_KEY=<运行 "openssl rand -hex 64" 生成>
CORS_ORIGINS=http://<公网IP>,http://<域名>
LLM_API_KEY=<你的 LLM API Key>
EMBEDDING_API_KEY=<你的 Embedding API Key>
ARXIV_CONTACT_EMAIL=<你的邮箱>
```

> 数据库密码可从 `~/papermate-db.env` 中获取。

**`nginx.conf`** — 1 处：

```nginx
server_name <公网IP或域名>;
```

### 2. 启动服务

```bash
cd /opt/papermate
chmod +x deploy.sh deploy-frontend.sh stop.sh

# 构建镜像、运行数据库迁移、启动 API + Celery workers
./deploy.sh

# 构建前端、部署到 Nginx
./deploy-frontend.sh

# 重载 Nginx
sudo nginx -t && sudo nginx -s reload
```

### 3. 验证

```bash
docker ps --filter "name=papermate-" --format "table {{.Names}}\t{{.Status}}"
curl http://127.0.0.1:8080/health
```

## 访问

| 地址 | 说明 |
|------|------|
| `http://<公网IP>` | 前端页面 |
| `http://<域名>` | 绑定域名后访问 |
| `http://<公网IP>:8080/health` | API 健康检查 |
| `http://<公网IP>:8080/docs` | API 文档 |

首次使用在登录页注册账户。

## 域名与 HTTPS

```bash
# 1. 域名服务商添加 A 记录 → 公网 IP
# 2. 修改 nginx.conf: server_name <域名>;
# 3. 修改 backend/.env.production: CORS_ORIGINS=https://<域名>
sudo nginx -t && sudo nginx -s reload

# HTTPS 证书（推荐）
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d <域名>
sudo systemctl enable certbot.timer
```

## 停止

```bash
cd /opt/papermate
./stop.sh
```

> 仅停止 API/Worker 容器，不影响 PostgreSQL 和 Redis。
