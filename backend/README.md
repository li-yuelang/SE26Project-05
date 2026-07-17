# arxiv-PaperMate backend

## Start locally

1. Install Python 3.11+ and uv.
2. **Local machine**: Start SSH tunnels to forward cloud PostgreSQL and Redis ports:

   ```bash
   # PostgreSQL (mapped to local 15432)
   ssh -N -L 15432:127.0.0.1:5432 root@10.119.4.37

   # Redis (mapped to local 6379)
   ssh -N -L 6379:127.0.0.1:6379 root@10.119.4.37
   ```

3. **Cloud server**: In this directory, run `uv sync`, then copy `.env.example` to `.env`.
4. Start PostgreSQL with `docker compose up -d postgres`. Ensure `REDIS_URL=redis://localhost:6379/0` and the PostgreSQL URL points to `localhost:15432` in `.env`.
5. Apply the schema with `uv run alembic upgrade head`.
6. Start the API with `uv run uvicorn app.main:app --reload --port 8080`.

Start the default worker for asynchronous paper analysis and scheduled dispatch:

```bash
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q default
```

Fetch runs use a dedicated single-concurrency queue. Start the arXiv worker and
the minute-level beat dispatcher separately:

```bash
uv run celery -A app.tasks.celery_app.celery_app worker --loglevel=info --pool=solo -Q arxiv --concurrency=1
uv run celery -A app.tasks.celery_app.celery_app beat --loglevel=info
```

Configure `LLM_API_KEY` and the optional `LLM_BASE_URL`, `LLM_MODEL`,
`EMBEDDING_BASE_URL`, and `EMBEDDING_MODEL` settings in `.env`. The analysis pipeline writes its durable state to
`papers.metadata_extra.analysis`; it does not create Markdown files on disk.

The API root is `http://localhost:8080/api`. The health endpoint is `GET /health`.
To launch all services in containers, run `docker compose up --build` from this directory.

`LLM_API_KEY` and `EMBEDDING_API_KEY` are optional. With a key, chat uses vector retrieval and
the configured OpenAI-compatible model. Without keys (or when a provider is unavailable),
it falls back to keyword reranking and a citation-grounded extractive answer.

## Wiki, Chat, and RAG

- `GET /api/wiki` returns concept statistics, category search results, relations, and activity.
- `/api/wiki/concepts` provides concept CRUD; relation create/delete lives below each concept.
- `GET /api/chat` returns the current user's conversations and messages.
- `/api/chat/conversations` provides conversation create/delete and message sending.
- `WS /api/chat/conversations/{id}/stream?token={access_token}` streams answer deltas and a final
  message payload.
- Every answer source includes `paperId` and `chunkIndex`; the corresponding original text is
  available from `GET /api/papers/{paper_id}/chunks/{chunk_index}`.

The RAG pipeline retrieves paper chunks, reranks them, selects a prompt for concept explanation,
method comparison, or research-lineage questions, generates a grounded answer, and persists the
citations with the assistant message.

## Shared contracts

- Success response: `{ "code": "OK", "message": "success", "data": ... }`
- Error response: `{ "code": "...", "message": "...", "details": ... }`
- Paginated data: `{ "items": [], "total": 0, "page": 1, "pageSize": 20 }`
- Authenticated APIs use `Authorization: Bearer <access_token>`.
- Authentication endpoints are `POST /auth/register`, `POST /auth/login`, and `GET /auth/me`.
- Paper analysis endpoints are `GET /papers/{paper_id}`, `GET /papers/{paper_id}/analysis`,
  and authenticated `POST /papers/{paper_id}/analysis?force=true`.
- Semantic chunk search is `GET /papers/search/semantic?q=...&paper_id=...&limit=10`.
- Fetch task management is available under `/tasks`: task configuration is
  private to its creator, while papers discovered by a run are written to the
  shared paper library.  Run history is available at `/tasks/{task_id}/runs`.

## Ownership

- Person A owns configuration, database, shared models, migrations, authentication, and cross-domain conventions.
- B-E add their endpoint modules under `app/api/v1/`, domain services under `app/services/`, and task modules under `app/tasks/`.
- Do not edit another domain's model without first agreeing on the relationship and migration.
