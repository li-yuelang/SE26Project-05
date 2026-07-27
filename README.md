# arxiv-PaperMate

AI-powered ArXiv paper reader with intelligent summaries, note-taking, and knowledge management.

## 项目结构

```text
SE26Project-05/
├── frontend/               React 前端（Vite + Ant Design）
├── backend/                FastAPI 后端（Python）
├── deploy.sh               云端部署脚本（后端）
├── deploy-frontend.sh      云端部署脚本（前端 + Nginx）
├── stop.sh                 停止 API/Worker 容器
├── nginx.conf              Nginx 反向代理配置
└── .github/                CI/CD 工作流
```

## 本地启动

需要提前安装 Node.js、Python 3.11+、`uv` 和 Docker Desktop。

### 1. 启动后端依赖（PostgreSQL + Redis）

在 `backend/` 目录下通过 Docker Compose 启动数据库和缓存：

```bash
cd backend
cp .env.example .env
uv sync
docker compose up -d postgres redis
uv run alembic upgrade head
```

`.env.example` 中的默认连接地址已指向本地 Docker 服务，复制为 `.env` 后可直接使用：
- `DATABASE_URL=postgresql+asyncpg://papermate:papermate@localhost:5432/papermate`
- `REDIS_URL=redis://localhost:6379/0`

如需论文分析和智能问答，在 `backend/.env` 中配置大模型及嵌入模型：

```env
LLM_API_KEY=your-api-key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSION=1536
```

`EMBEDDING_API_KEY` 和 `EMBEDDING_BASE_URL` 留空时会复用大模型的密钥和接口地址。

### 2. 启动 API 和后台任务

在第一个终端运行 FastAPI：

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8080
```

论文异步分析和 arXiv 抓取分别使用两个 Celery 队列，需要启动两个 worker：

```bash
# analysis 队列：论文解析和 outbox 派发
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q analysis --concurrency=2

# beat：定期派发 outbox、恢复僵尸运行和调度抓取任务
uv run celery -A app.tasks.celery_app.celery_app beat --loglevel=info

# arxiv 队列：抓取任务（单并发，遵守 arXiv 请求频率限制）
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q arxiv --concurrency=1
```

后端启动后可访问：

- 健康检查：<http://localhost:8080/health>
- API 文档：<http://localhost:8080/docs>

### 3. 启动前端

在第三个终端运行：

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

访问 <http://localhost:3000>，首次使用可在登录页面创建账户。开发环境会将浏览器的
`/api` 请求代理到 `http://127.0.0.1:8080`。

连接远程后端时，修改 `frontend/.env.local`：

```env
VITE_API_MODE=http
VITE_API_BASE_URL=/api
VITE_BACKEND_TARGET=http://远程服务器地址:8080
```

修改环境变量后需要重启 Vite。

### 一键启动脚本

项目根目录下提供了跨平台启动脚本，可自动启动 Docker 依赖并打开多个终端窗口运行所有服务：

| 平台 | 脚本 | 执行方式 |
|------|------|----------|
| Windows | `start-local.ps1` | 在项目目录下右键 "Open in Terminal"，执行 `.\start-local.ps1` |
| macOS | `start-mac.sh` | `chmod +x start-mac.sh && ./start-mac.sh` |
| Linux | `start-linux.sh` | `chmod +x start-linux.sh && ./start-linux.sh` |

> **Windows 注意**：如提示执行策略限制，先运行 `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`。
>
> **Linux 注意**：脚本会自动检测 gnome-terminal / konsole / xfce4-terminal / lxterminal / xterm，未安装则需先安装其一。

`start-local.ps1` 会先通过 Docker Compose 启动 PostgreSQL 和 Redis，然后打开以下窗口：

1. **FastAPI 后端** — `uv run uvicorn app.main:app --workers 2 --port 8080`
2. **Celery Analysis Worker** — `uv run celery ... worker --loglevel=info --pool=solo -Q analysis --concurrency=2`
3. **Celery arXiv Worker** — `uv run celery ... worker --loglevel=info --pool=solo -Q arxiv --concurrency=1`
4. **Celery Beat** — `uv run celery ... beat --loglevel=info`
5. **前端 Vite** — `npm run dev`

## 前端

```bash
cd frontend
npm install
npm run dev          # 开发模式启动（默认端口 3000）
npm run build        # 生产构建
```

### 前端分层

```text
frontend/src/
├── components/  可复用、无领域数据依赖的 UI 组件
├── data/        Mock 数据，仅允许 services 引用
├── hooks/       通用 React 状态与生命周期逻辑
├── layouts/     应用外壳、导航与 Outlet 布局
├── pages/       路由页面，组合 UI 并调用 services
├── services/    领域 API、数据适配、Mock/HTTP 切换
└── styles/      基础、布局、响应式与领域页面样式
```

依赖方向固定为：

```text
pages → services → data（Mock 模式）
                 → HTTP API（HTTP 模式）
pages → components / hooks / layouts
```

样式统一从 `frontend/src/styles/index.css` 引入。新增页面样式应放进对应领域文件；只有颜色变量、全局重置和字体规则可以进入 `base.css`，应用外壳与导航规则分别放在 `app-layout.css` 和 `sidebar.css`。

页面不得直接导入 `src/data`。后端字段与前端视图模型不一致时，应在对应 service 中转换，避免把接口细节扩散到页面。

### Mock 与真实后端切换

复制 `frontend/.env.example` 为 `frontend/.env.local`。当前默认配置使用真实后端：

```env
VITE_API_MODE=http
VITE_API_BASE_URL=/api
VITE_BACKEND_TARGET=http://127.0.0.1:8080
```

需要独立调试页面、暂时不连接后端时可切回 Mock：

```env
VITE_API_MODE=mock
```

页面调用方式不会变化。真实后端路径、请求参数或响应字段发生变化时，只修改 `frontend/src/services` 中对应领域文件。

`frontend/src/services/apiClient.js` 统一处理：

- API Base URL；
- JSON 编解码；
- Cookie 凭证；
- Query 参数；
- HTTP 错误到 `ApiError` 的转换；
- Mock/HTTP 运行模式选择。

### Service 返回约定

列表接口建议返回：

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "pageSize": 20
}
```

HTTP 响应可以直接返回业务数据，也可以包在 `data` 字段中。错误响应建议统一为：

```json
{
  "code": "PAPER_NOT_FOUND",
  "message": "论文不存在",
  "details": null
}
```

## 后端

```bash
cd backend
uv sync
docker compose up -d postgres
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
```

完整启动流程和两个 Celery worker 命令见上方"本地启动"。

---

## 云端部署（Docker 独立模式，无 docker-compose）

本项目云端采用 **host 网络模式**，API / Worker 容器通过 `--network host` 直连宿主机已有的 PostgreSQL 和 Redis，前端通过 Nginx 统一对外提供服务。

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

### 云端要求

| 依赖 | 说明 |
|------|------|
| Docker | 已安装（不需要 docker-compose） |
| PostgreSQL + pgvector | 已运行，容器名 `papermate-postgres`，监听 `127.0.0.1:5432` |
| Redis | 已运行，容器名 `redis`，监听 `0.0.0.0:6379` |
| Nginx | 已安装，用于反向代理和前端静态文件 |
| 端口 | 80（Nginx）、8080（API，仅 localhost） |
| 防火墙/安全组 | 放行 80（HTTP）和 443（HTTPS）端口 |

### 部署步骤

#### 1. 上传代码到云服务器

```bash
# 在本地执行
scp -r ./SE26Project-05 root@<公网IP>:/opt/papermate
```

#### 2. 填写配置文件

云端登录后，编辑以下两个文件中的 `<...>` 占位符：

**`/opt/papermate/backend/.env.production`** — 共 6 处需要手动填写：

```env
DATABASE_URL=postgresql+asyncpg://papermate:<数据库密码>@127.0.0.1:5432/papermate
JWT_SECRET_KEY=<运行 "openssl rand -hex 64" 生成>
CORS_ORIGINS=http://<公网IP>,http://<域名>
LLM_API_KEY=<你的 LLM API Key>
EMBEDDING_API_KEY=<你的 Embedding API Key>
ARXIV_CONTACT_EMAIL=<你的邮箱>
```

> 数据库密码可从云端的 `~/papermate-db.env` 文件中获取（如果存在）。

**`/opt/papermate/nginx.conf`** — 1 处：

```nginx
server_name <公网IP或域名>;
```

#### 3. 运行部署脚本

```bash
cd /opt/papermate
chmod +x deploy.sh deploy-frontend.sh stop.sh

# 启动后端（构建镜像、运行迁移、启动 API + Celery workers）
./deploy.sh

# 部署前端（构建前端、复制到 Nginx 目录、配置 Nginx）
./deploy-frontend.sh

# 验证 Nginx 配置并重载
sudo nginx -t && sudo nginx -s reload
```

#### 4. 验证部署

```bash
# 检查容器状态
docker ps --filter "name=papermate-" --format "table {{.Names}}\t{{.Status}}"

# API 健康检查
curl http://127.0.0.1:8080/health

# 外部访问测试（在本地浏览器或 curl）
curl http://<公网IP>/health
```

### 访问方式

| 地址 | 说明 |
|------|------|
| `http://<公网IP>` | 浏览器直接访问前端页面 |
| `http://<域名>` | 绑定域名后访问 |
| `http://<公网IP>:8080/health` | API 健康检查 |
| `http://<公网IP>:8080/docs` | API 文档（开发调试用） |

首次使用需在登录页面注册账户。

### 使用域名

1. 在域名服务商处添加 A 记录，将域名指向云服务器公网 IP
2. 修改 `nginx.conf`：`server_name <你的域名>;`
3. 修改 `backend/.env.production`：`CORS_ORIGINS=https://<你的域名>`
4. 重载 Nginx：`sudo nginx -t && sudo nginx -s reload`

#### 开启 HTTPS（推荐）

```bash
sudo apt install certbot python3-certbot-nginx -y
sudo certbot --nginx -d <你的域名>
sudo systemctl enable certbot.timer
```

### 停止服务

```bash
cd /opt/papermate
./stop.sh
```

> 停止脚本仅关闭 API 和 Celery worker 容器，不会影响 PostgreSQL 和 Redis。

### 部署文件说明

| 文件 | 用途 |
|------|------|
| `deploy.sh` | 启动全部后端服务（host 网络模式，依赖已有 PG/Redis） |
| `deploy-frontend.sh` | 构建前端并配置 Nginx |
| `stop.sh` | 停止 API 和 Worker 容器 |
| `nginx.conf` | Nginx 反向代理配置模板 |
| `backend/.env.production` | 后端生产环境变量（需填写 API Key 等敏感信息） |
| `frontend/.env.production` | 前端构建时的环境变量（同源部署无需修改） |
| `backend/Dockerfile` | 后端镜像构建（Python 3.12 + pip install + uvicorn） |
| `frontend/Dockerfile` | 前端多阶段构建（Node 构建 + Nginx 运行时） |
