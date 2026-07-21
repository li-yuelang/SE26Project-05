"""Paper list/detail, analysis control and semantic search endpoints."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, Response, status
from sqlalchemy import or_, select

from app.api.deps import CurrentUser, DbSession
from app.config import settings
from app.core.embedding import EmbeddingProviderError, get_embedding_provider
from app.core.exceptions import AppError
from app.models.paper import Paper, PaperAnalysisRun, PaperChunk, UserPaper
from app.schemas.common import success
from app.schemas.paper import (
    PaperBatchRequest,
    PaperFilterParams,
    PaperListResponse,
    PaperUpdateRequest,
)
from app.services import paper_service
from app.services.analysis_runs import create_analysis_run, get_current_analysis_run
from app.services.analysis_state import get_analysis_metadata, new_analysis_version
from app.tasks.paper_tasks import process_paper
from sqlalchemy.exc import IntegrityError

router = APIRouter(prefix="/papers", tags=["papers"])


def _analysis_view(paper: Paper, run: PaperAnalysisRun | None = None) -> dict[str, Any]:
    if run is not None:
        return {
            "paperId": str(paper.id),
            "runId": str(run.id),
            "status": run.status,
            "stage": run.stage,
            "error": run.error_message,
            "errorCode": run.error_code,
            "taskId": run.celery_task_id,
            "attempt": run.attempt,
            "force": run.force,
            "model": run.llm_model,
            "embeddingModel": run.embedding_model,
            "promptVersion": run.prompt_version,
            "pipelineVersion": run.pipeline_version,
            "analysisVersion": run.analysis_version,
            "queuedAt": run.queued_at.isoformat() if run.queued_at else None,
            "startedAt": run.started_at.isoformat() if run.started_at else None,
            "heartbeatAt": run.heartbeat_at.isoformat() if run.heartbeat_at else None,
            "retryAfterAt": run.retry_after_at.isoformat() if run.retry_after_at else None,
            "finishedAt": run.finished_at.isoformat() if run.finished_at else None,
        }
    metadata = get_analysis_metadata(paper)
    return {
        "paperId": str(paper.id),
        "status": metadata.get("status") or paper.parsed_status,
        "stage": metadata.get("stage")
        or ("pending" if paper.parsed_status == "pending" else "unknown"),
        "error": metadata.get("error"),
        "taskId": metadata.get("task_id"),
        "model": metadata.get("model"),
        "embeddingModel": metadata.get("embedding_model"),
        "promptVersion": metadata.get("prompt_version"),
        "analysisVersion": metadata.get("analysis_version"),
        "startedAt": metadata.get("started_at"),
        "completedAt": metadata.get("completed_at"),
        "updatedAt": metadata.get("updated_at"),
    }


@router.get("")
async def list_papers(
    db: DbSession,
    user: CurrentUser,
    query: str | None = Query(default=None, max_length=500),
    category: str | None = Query(default=None, max_length=100),
    author: str | None = Query(default=None, max_length=200),
    parsed_status: str | None = Query(default=None, max_length=32),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=10000),
) -> dict:
    params = PaperFilterParams(
        query=query,
        category=category,
        author=author,
        parsed_status=parsed_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    items, total = await paper_service.list_papers(db, user.id, params)
    resp = PaperListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )
    return success(resp.model_dump(by_alias=True))


@router.delete("/batch")
async def delete_papers(
    body: PaperBatchRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    deleted_ids = await paper_service.delete_papers(db, user.id, body.paper_ids)
    return success(
        {
            "deletedIds": [str(paper_id) for paper_id in deleted_ids],
            "deletedCount": len(deleted_ids),
        },
        "Papers deleted",
    )


@router.get("/search/semantic")
async def semantic_search(
    db: DbSession,
    user: CurrentUser,
    q: str = Query(min_length=1, max_length=2000),
    paper_id: UUID | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    try:
        vectors = await get_embedding_provider().embed([q])
        query_vector = vectors[0]
    except (EmbeddingProviderError, IndexError) as exc:
        raise AppError(
            "Semantic search embedding failed",
            code="EMBEDDING_ERROR",
            status_code=503,
            details=str(exc),
        ) from exc

    distance = PaperChunk.embedding.cosine_distance(query_vector)
    score = (1 - distance).label("score")
    statement = (
        select(PaperChunk, Paper, score)
        .join(Paper, Paper.id == PaperChunk.paper_id)
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(
            PaperChunk.embedding.is_not(None),
            UserPaper.user_id == user.id,
            or_(
                Paper.active_analysis_run_id.is_(None),
                PaperChunk.analysis_run_id == Paper.active_analysis_run_id,
            ),
        )
    )
    if paper_id:
        statement = statement.where(PaperChunk.paper_id == paper_id)
    statement = statement.order_by(distance).limit(limit)

    rows = (await db.execute(statement)).all()
    items = [
        {
            "chunkId": str(chunk.id),
            "paperId": str(paper.id),
            "paperTitle": paper.title,
            "section": chunk.section_title,
            "chunkIndex": chunk.chunk_index,
            "content": chunk.content,
            "score": max(0.0, min(1.0, float(score_value))),
        }
        for chunk, paper, score_value in rows
    ]
    return success({"items": items, "total": len(items), "query": q})


@router.get("/{paper_id}/analysis")
async def get_analysis(paper_id: UUID, db: DbSession, user: CurrentUser) -> dict[str, Any]:
    paper = await db.scalar(
        select(Paper).join(UserPaper).where(Paper.id == paper_id, UserPaper.user_id == user.id)
    )
    if paper is None:
        raise AppError("论文不存在", code="PAPER_NOT_FOUND", status_code=404)
    run = await get_current_analysis_run(db, paper_id)
    return success(_analysis_view(paper, run))


@router.post("/{paper_id}/analysis", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    paper_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    # A few old service-level tests use a deliberately tiny fake session.  The
    # compatibility branch keeps those tests useful; real AsyncSession always
    # takes the transactional outbox path below.
    if not hasattr(db, "add"):
        paper = await db.scalar(select(Paper).where(Paper.id == paper_id).with_for_update())
        if paper is None:
            raise AppError("论文不存在", code="PAPER_NOT_FOUND", status_code=404)
        metadata = get_analysis_metadata(paper)
        if paper.parsed_status == "processing":
            return success(_analysis_view(paper), "analysis already in progress")
        if paper.parsed_status == "completed" and not force:
            return success(_analysis_view(paper), "analysis already completed")
        analysis_version = new_analysis_version()
        paper.parsed_status = "processing"
        paper.metadata_extra = {
            **(paper.metadata_extra or {}),
            "analysis": {
                **metadata,
                "status": "processing",
                "stage": "queued",
                "error": None,
                "analysis_version": analysis_version,
                "model": settings.llm_model,
                "embedding_model": settings.embedding_model,
                "prompt_version": settings.analysis_prompt_version,
            },
        }
        await db.commit()
        async_result = process_paper.delay(str(paper.id), force=force)
        paper.metadata_extra["analysis"]["task_id"] = getattr(async_result, "id", None)
        await db.commit()
        return success(_analysis_view(paper), "analysis task queued")

    paper = await db.scalar(
        select(Paper)
        .join(UserPaper)
        .where(Paper.id == paper_id, UserPaper.user_id == current_user.id)
        .with_for_update()
    )
    if paper is None:
        raise AppError("论文不存在", code="PAPER_NOT_FOUND", status_code=404)
    try:
        run, created = await create_analysis_run(
            db,
            paper.id,
            force=force,
            requested_by=getattr(current_user, "id", None),
        )
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        refreshed = await db.get(Paper, paper_id)
        run = await get_current_analysis_run(db, paper_id)
        if refreshed is None or run is None:
            raise AppError(
                "无法创建论文分析任务",
                code="ANALYSIS_QUEUE_ERROR",
                status_code=503,
                details=str(exc),
            ) from exc
        paper = refreshed
        created = False
    except Exception as exc:
        raise AppError(
            "无法创建论文分析任务",
            code="ANALYSIS_QUEUE_ERROR",
            status_code=503,
            details=str(exc),
        ) from exc
    refreshed = await db.get(Paper, paper_id)
    return success(
        _analysis_view(refreshed or paper, run),
        "analysis task queued" if created else "analysis already in progress or completed",
    )


@router.get("/{paper_id}")
async def get_paper_detail(
    paper_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    detail = await paper_service.get_paper_detail(db, paper_id, user.id)
    return success(detail.model_dump(mode="json"))


@router.get("/{paper_id}/chunks/{chunk_index}")
async def get_paper_chunk(
    paper_id: UUID,
    chunk_index: int,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    return success(await paper_service.get_paper_chunk(db, user.id, paper_id, chunk_index))


@router.patch("/{paper_id}")
async def update_paper(
    paper_id: UUID,
    body: PaperUpdateRequest,
    db: DbSession,
    user: CurrentUser,
) -> dict:
    # Paper is a shared cache.  Keep this route explicit for clients that have
    # not migrated yet, but never let a library member write global content.
    detail = await paper_service.update_paper(db, user.id, paper_id, body)
    return success(detail.model_dump(mode="json"))


@router.delete("/{paper_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_paper(
    paper_id: UUID,
    db: DbSession,
    user: CurrentUser,
) -> Response:
    await paper_service.delete_paper(db, user.id, paper_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
