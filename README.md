# arxiv-PaperMate

AI-powered ArXiv paper reader with intelligent summaries, note-taking, and knowledge management.

## 项目结构

```text
SE26Project-05/
├── frontend/          React 前端（Vite + Ant Design）
├── backend/           FastAPI 后端（Python）
└── .github/           CI/CD 工作流
```

## 本地启动

需要提前安装 Node.js、Python 3.11+、`uv` 和 Docker（或 OrbStack）。

### 1. 启动后端依赖

**本地**运行 SSH 端口转发，将云端 PostgreSQL 和 Redis 映射到本地：

```bash
# PostgreSQL 端口映射（映射到本地 15432）
ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37

# Redis 端口映射（映射到本地 6379）
ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37
```

> 以上两条 SSH 隧道会保持前台运行，请分别在独立终端中执行，或加 `-f` 参数后台运行。

**云端**执行以下步骤启动后端服务：

```bash
cd backend
cp .env.example .env
uv sync
docker compose up -d postgres
uv run alembic upgrade head
```

> 确保 `backend/.env` 中配置了正确的连接地址：
> - `REDIS_URL=redis://localhost:6379/0`
> - PostgreSQL 连接地址需指向 `localhost:15432`

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

论文异步分析需要在第二个终端启动 Celery worker：

```bash
cd backend
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo
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

完整启动流程和 Celery worker 命令见上方“本地启动”。
