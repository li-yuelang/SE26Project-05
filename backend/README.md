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

## Ownership

- Person A owns configuration, database, shared models, migrations, authentication, and cross-domain conventions.
- B-E add their endpoint modules under `app/api/v1/`, domain services under `app/services/`, and task modules under `app/tasks/`.
- Do not edit another domain's model without first agreeing on the relationship and migration.
