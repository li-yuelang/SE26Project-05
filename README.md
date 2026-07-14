# arxiv-PaperMate

AI-powered ArXiv paper reader with intelligent summaries, note-taking, and knowledge management.

## 项目结构

```text
SE26Project-05/
├── frontend/          React 前端（Vite + Ant Design）
├── backend/           FastAPI 后端（Python）
└── .github/           CI/CD 工作流
```

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

复制 `frontend/.env.example` 为 `frontend/.env.local`。默认配置使用 Mock API：

```env
VITE_API_MODE=mock
```

接入后端时改为：

```env
VITE_API_MODE=http
VITE_API_BASE_URL=http://localhost:8080/api
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
# 使用 uv 管理依赖
uv sync
uv run uvicorn app.main:app --reload
```
