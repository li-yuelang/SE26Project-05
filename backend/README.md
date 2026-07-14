# arxiv-PaperMate backend

## Start locally

1. Install Python 3.11+ and uv.
2. In this directory, run `uv sync`, then copy `.env.example` to `.env`.
3. Start PostgreSQL and Redis with `docker compose up -d postgres redis`.
4. Apply the schema with `uv run alembic upgrade head`.
5. Start the API with `uv run uvicorn app.main:app --reload --port 8080`.

The API root is `http://localhost:8080/api`. The health endpoint is `GET /health`.
To launch all services in containers, run `docker compose up --build` from this directory.

## Shared contracts

- Success response: `{ "code": "OK", "message": "success", "data": ... }`
- Error response: `{ "code": "...", "message": "...", "details": ... }`
- Paginated data: `{ "items": [], "total": 0, "page": 1, "pageSize": 20 }`
- Authenticated APIs use `Authorization: Bearer <access_token>`.
- Authentication endpoints are `POST /auth/register`, `POST /auth/login`, and `GET /auth/me`.

## Ownership

- Person A owns configuration, database, shared models, migrations, authentication, and cross-domain conventions.
- B-E add their endpoint modules under `app/api/v1/`, domain services under `app/services/`, and task modules under `app/tasks/`.
- Do not edit another domain's model without first agreeing on the relationship and migration.
