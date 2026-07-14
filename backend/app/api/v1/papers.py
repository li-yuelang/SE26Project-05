"""Paper detail, analysis control and semantic chunk search endpoints."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, DbSession
from app.config import settings
from app.core.embedding import EmbeddingProviderError, get_embedding_provider
from app.core.exceptions import AppError
from app.models.concept import PaperConcept
from app.models.paper import Paper, PaperChunk, PaperCitation
from app.services.analysis_state import get_analysis_metadata, new_analysis_version
from app.tasks.paper_tasks import process_paper
from app.schemas.common import success


router = APIRouter(prefix="/papers", tags=["papers"])


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _structured_content(paper: Paper) -> dict[str, Any]:
    content = dict(paper.structured_content or {})
    return {
        "summary": str(content.get("summary") or ""),
        "concept": str(content.get("concept") or ""),
        "methods": str(content.get("methods") or ""),
        **{key: value for key, value in content.items() if key not in {"summary", "concept", "methods"}},
    }


def _analysis_view(paper: Paper) -> dict[str, Any]:
    metadata = get_analysis_metadata(paper)
    return {
        "paperId": str(paper.id),
        "status": metadata.get("status") or paper.parsed_status,
        "stage": metadata.get("stage") or ("pending" if paper.parsed_status == "pending" else "unknown"),
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


async def _load_paper(db: DbSession, paper_id: UUID) -> Paper | None:
    return await db.scalar(
        select(Paper)
        .options(
            selectinload(Paper.concepts).selectinload(PaperConcept.concept),
            selectinload(Paper.outgoing_citations).selectinload(PaperCitation.target_paper),
        )
        .where(Paper.id == paper_id)
    )


@router.get("/search/semantic")
async def semantic_search(
    db: DbSession,
    q: str = Query(min_length=1, max_length=2000),
    paper_id: UUID | None = Query(default=None),
    limit: int = Query(default=10, ge=1, le=50),
) -> dict[str, Any]:
    try:
        query_vector = (await get_embedding_provider().embed([q]))[0]
    except (EmbeddingProviderError, IndexError) as exc:
        raise AppError("Semantic search embedding failed", "EMBEDDING_ERROR", 503, str(exc)) from exc
    distance = PaperChunk.embedding.cosine_distance(query_vector)
    score = (1 - distance).label("score")
    statement = (
        select(PaperChunk, Paper, score)
        .join(Paper, Paper.id == PaperChunk.paper_id)
        .where(PaperChunk.embedding.is_not(None))
        .order_by(distance)
    )
    if paper_id:
        statement = statement.where(PaperChunk.paper_id == paper_id)
    statement = statement.limit(limit)
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
async def get_analysis(paper_id: UUID, db: DbSession) -> dict[str, Any]:
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise AppError("论文不存在", "PAPER_NOT_FOUND", 404)
    return success(_analysis_view(paper))


@router.post("/{paper_id}/analysis", status_code=status.HTTP_202_ACCEPTED)
async def trigger_analysis(
    paper_id: UUID,
    db: DbSession,
    current_user: CurrentUser,
    force: bool = Query(default=False),
) -> dict[str, Any]:
    del current_user  # Dependency enforces authentication; the endpoint is user-agnostic.
    paper = await db.scalar(select(Paper).where(Paper.id == paper_id).with_for_update())
    if paper is None:
        raise AppError("论文不存在", "PAPER_NOT_FOUND", 404)
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
    try:
        async_result = process_paper.delay(str(paper.id), force=force)
        task_id = getattr(async_result, "id", None)
        # Eager mode can finish before this request regains control.  Do not
        # overwrite a completed state with a queued task id in that case.
        refreshed = await db.get(Paper, paper.id)
        if refreshed is not None and refreshed.parsed_status == "processing":
            refreshed.metadata_extra = {
                **(refreshed.metadata_extra or {}),
                "analysis": {
                    **get_analysis_metadata(refreshed),
                    "task_id": task_id,
                },
            }
            await db.commit()
            paper = refreshed
        else:
            paper = refreshed or paper
    except Exception as exc:
        paper = await db.get(Paper, paper.id)
        if paper is not None:
            paper.parsed_status = "failed"
            paper.metadata_extra = {
                **(paper.metadata_extra or {}),
                "analysis": {
                    **get_analysis_metadata(paper),
                    "status": "failed",
                    "stage": "failed",
                    "error": str(exc)[:4000],
                },
            }
            await db.commit()
        raise AppError("无法创建论文分析任务", "ANALYSIS_QUEUE_ERROR", 503, str(exc)) from exc
    return success(_analysis_view(paper), "analysis task queued")


@router.get("/{paper_id}")
async def get_paper(paper_id: UUID, db: DbSession) -> dict[str, Any]:
    paper = await _load_paper(db, paper_id)
    if paper is None:
        raise AppError("论文不存在", "PAPER_NOT_FOUND", 404)
    concepts = [
        {
            "id": str(link.concept.id),
            "name": link.concept.name,
            "aliases": link.concept.aliases or [],
            "description": link.concept.description,
            "relevance": link.relevance,
            "evidence": link.evidence,
        }
        for link in paper.concepts
    ]
    citations = [
        {
            "id": str(citation.id),
            "paperId": str(citation.target_paper.id),
            "arxivId": citation.target_paper.arxiv_id,
            "title": citation.target_paper.title,
            "context": citation.context,
            "confidence": citation.confidence,
        }
        for citation in paper.outgoing_citations
        if citation.target_paper is not None
    ]
    data = {
        "id": str(paper.id),
        "paperId": str(paper.id),
        "arxivId": paper.arxiv_id,
        "title": paper.title,
        "authors": paper.authors or [],
        "abstract": paper.abstract,
        "categories": paper.categories or [],
        "primaryCategory": paper.primary_category,
        "publishedAt": _iso(paper.published_at),
        "updatedAt": _iso(paper.updated_at_source),
        "pdfUrl": paper.pdf_url,
        "arxivUrl": paper.arxiv_url,
        "parsedStatus": paper.parsed_status,
        "structuredContent": _structured_content(paper),
        "concepts": concepts,
        "citations": citations,
        "parsedReferences": citations,
        "analysis": _analysis_view(paper),
        "createdAt": _iso(paper.created_at),
        "updated": _iso(paper.updated_at),
    }
    return success(data)
