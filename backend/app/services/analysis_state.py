"""Small helpers for the durable analysis state stored on ``Paper``."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.paper import Paper


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_analysis_version() -> str:
    return f"{settings.analysis_version}-{uuid4().hex[:12]}"


def get_analysis_metadata(paper: Paper) -> dict[str, Any]:
    metadata = paper.metadata_extra or {}
    analysis = metadata.get("analysis") if isinstance(metadata, dict) else None
    return dict(analysis) if isinstance(analysis, dict) else {}


async def set_analysis_state(
    db: AsyncSession,
    paper_id: UUID,
    *,
    status: str,
    stage: str,
    error: str | None = None,
    task_id: str | None = None,
    analysis_version: str | None = None,
    model: str | None = None,
    embedding_model: str | None = None,
    prompt_version: str | None = None,
    commit: bool = True,
) -> Paper:
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise LookupError(f"Paper {paper_id} does not exist")
    previous = get_analysis_metadata(paper)
    analysis = {
        **previous,
        "status": status,
        "stage": stage,
        "error": error,
        "updated_at": utc_now(),
    }
    if task_id is not None:
        analysis["task_id"] = task_id
    if analysis_version is not None:
        analysis["analysis_version"] = analysis_version
    if model is not None:
        analysis["model"] = model
    if embedding_model is not None:
        analysis["embedding_model"] = embedding_model
    if prompt_version is not None:
        analysis["prompt_version"] = prompt_version
    if status == "processing" and (
        not previous.get("started_at")
        or (analysis_version is not None and analysis_version != previous.get("analysis_version"))
    ):
        analysis["started_at"] = utc_now()
        analysis.pop("completed_at", None)
        analysis.pop("failed_at", None)
    if status == "completed":
        analysis["completed_at"] = utc_now()
    if status == "failed":
        analysis["failed_at"] = utc_now()
    paper.parsed_status = status
    paper.metadata_extra = {**(paper.metadata_extra or {}), "analysis": analysis}
    if commit:
        await db.commit()
        await db.refresh(paper)
    return paper


async def mark_analysis_failed(
    db: AsyncSession, paper_id: UUID, error: str, *, task_id: str | None = None
) -> None:
    try:
        await set_analysis_state(
            db,
            paper_id,
            status="failed",
            stage="failed",
            error=error[:4000],
            task_id=task_id,
        )
    except LookupError:
        await db.rollback()


async def mark_analysis_retrying(
    db: AsyncSession, paper_id: UUID, error: str, *, retry_number: int
) -> None:
    await set_analysis_state(
        db,
        paper_id,
        status="processing",
        stage=f"retrying:{retry_number}",
        error=error[:4000],
    )
