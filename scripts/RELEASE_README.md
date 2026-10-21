# PaperMate 发布包

## 内容与版本

- `frontend/`：Vite 生产静态文件，`build_info.json` 记录版本。
- `backend/*.whl`：Python 安装包，内含相同的 `app/build_info.json`。
- `backend/requirements.txt`：从 uv.lock 导出的运行依赖（含哈希）。
- `backend/alembic/`、`alembic.ini`：数据库迁移文件。
- `BUILD_INFO.json`：版本号、构建号、提交号及 Actions 链接。

发布版本以 BUILD_INFO.json 和 /version 为准。Python 分发元数据中的
0.1.0 是当前项目内部包版本，并不等同于整个前后端发布版本。
安装需要联网、Python 3.12.10 和 uv 0.11.28；此包不是离线独立程序。

## Windows PowerShell

在解压后的包根目录运行：

```powershell
uv venv --python 3.12.10 .venv
uv pip install --python .venv\Scripts\python.exe --require-hashes -r backend\requirements.txt
uv pip install --python .venv\Scripts\python.exe --no-deps (Get-ChildItem backend\*.whl).FullName
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 18080
```

另开终端查询，验证后在服务终端按 Ctrl+C 停止：

```powershell
Invoke-RestMethod http://127.0.0.1:18080/version | ConvertTo-Json -Depth 5
```

## Linux

```bash
uv venv --python 3.12.10 .venv
uv pip install --python .venv/bin/python --require-hashes -r backend/requirements.txt
uv pip install --python .venv/bin/python --no-deps backend/*.whl
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 18080
# 在另一终端运行：curl -fsS http://127.0.0.1:18080/version
```

## 验证与追溯

在小组项目完整克隆中运行（将文件名替换为实际下载的 Release 附件）：

```bash
python scripts/trace.py dist/papermate_1.0.0.tar.gz
```

将 .sha256 附件放在包旁边。追溯脚本不解压执行包内代码，核对校验和、
前后端版本信息、Actions 链接的仓库与运行 ID，以及提交是否在 main 历史中。
构建号在每个工作流内分别计数，run_id 和链接用于定位唯一运行。
校验和不是签名；应独立保留发布时的原始值，以发现包和校验和一起被替换。

## 业务运行范围

/version 验证安装包来源，不代表全部业务功能都已验证。
完整业务需要 PostgreSQL、Redis、Celery 和外部服务配置。
数据库迁移在配置连接后从 backend 目录运行，使用已安装环境中的 alembic。
回退程序不会自动回退数据库，必须先确认 schema 兼容性。
前端需要静态服务器与 /api 反向代理；Vite 的开发代理不随静态包运行。
包中不提供真实环境配置，部署时自行配置环境变量。
