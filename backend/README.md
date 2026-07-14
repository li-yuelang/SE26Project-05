# arxiv-PaperMate backend

## Start locally

1. Install Python 3.11+ and uv.
2. In this directory, run `uv sync`, then copy `.env.example` to `.env`.
3. Start PostgreSQL and Redis with `docker compose up -d postgres redis`.
4. Apply the schema with `uv run alembic upgrade head`.
5. Start the API with `uv run uvicorn app.main:app --reload --port 8080`.

For asynchronous paper analysis, start the worker in a second terminal:

```bash
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info
```

Configure `LLM_API_KEY` and the optional OpenAI-compatible base/model settings
in `.env`.  The analysis pipeline writes its durable state to
`papers.metadata_extra.analysis`; it does not create Markdown files on disk.

The API root is `http://localhost:8080/api`. The health endpoint is `GET /health`.
To launch all services in containers, run `docker compose up --build` from this directory.

## Shared contracts

- Success response: `{ "code": "OK", "message": "success", "data": ... }`
- Error response: `{ "code": "...", "message": "...", "details": ... }`
- Paginated data: `{ "items": [], "total": 0, "page": 1, "pageSize": 20 }`
- Authenticated APIs use `Authorization: Bearer <access_token>`.
- Authentication endpoints are `POST /auth/register`, `POST /auth/login`, and `GET /auth/me`.
- Paper analysis endpoints are `GET /papers/{paper_id}`, `GET /papers/{paper_id}/analysis`,
  and authenticated `POST /papers/{paper_id}/analysis?force=true`.
- Semantic chunk search is `GET /papers/search/semantic?q=...&paper_id=...&limit=10`.

## Ownership

- Person A owns configuration, database, shared models, migrations, authentication, and cross-domain conventions.
- B-E add their endpoint modules under `app/api/v1/`, domain services under `app/services/`, and task modules under `app/tasks/`.
- Do not edit another domain's model without first agreeing on the relationship and migration.
