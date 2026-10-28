"""论文业务逻辑服务层 — CRUD + 搜索 + arXiv 入库。"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.core.exceptions import AppError
from app.models.learning import Bookmark
from app.models.concept import PaperConcept
from app.models.paper import Paper, PaperChunk, UserPaper
from app.schemas.paper import ConceptRef, PaperDetail, PaperFilterParams, PaperListItem, PaperRef, PaperUpdateRequest

logger = logging.getLogger(__name__)


async def list_papers(
    db: AsyncSession,
    user_id: UUID,
    params: PaperFilterParams,
) -> tuple[list[PaperListItem], int]:
    """分页查询论文列表，支持关键词搜索、分类筛选、日期范围。"""
    filters = [UserPaper.user_id == user_id]

    # 全文搜索：使用 pg_trgm 或 ilike
    if params.query:
        like_pattern = f"%{params.query}%"
        filters.append(
            or_(
                Paper.title.ilike(like_pattern),
                Paper.abstract.ilike(like_pattern),
                Paper.arxiv_id.ilike(like_pattern),
            )
        )
    if params.category:
        filters.append(Paper.primary_category == params.category)
    if params.author:
        filters.append(Paper.authors.any(params.author))
    if params.parsed_status:
        filters.append(Paper.parsed_status == params.parsed_status)
    if params.date_from:
        try:
            dt_from = datetime.strptime(params.date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            filters.append(Paper.published_at >= dt_from)
        except ValueError:
            pass
    if params.date_to:
        try:
            dt_to = datetime.strptime(params.date_to, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
            filters.append(Paper.published_at <= dt_to)
        except ValueError:
            pass

    # Count – direct join so PostgreSQL can use index-only scans
    count_q = (
        select(func.count(Paper.id))
        .select_from(Paper)
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(*filters)
    )
    total = (await db.scalar(count_q)) or 0

    # Data page
    query = (
        select(Paper)
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(*filters)
        .order_by(Paper.published_at.desc().nullslast())
        .offset((params.page - 1) * params.page_size)
        .limit(params.page_size)
    )
    rows = (await db.execute(query)).scalars().all()

    items = [PaperListItem.model_validate(r) for r in rows]
    return items, total


async def get_paper_detail(db: AsyncSession, paper_id: UUID, user_id: UUID) -> PaperDetail:
    """获取论文详情（含结构化内容、元数据、关联概念和引用论文）。"""
    paper = await db.scalar(
        select(Paper)
        .options(selectinload(Paper.concepts).selectinload(PaperConcept.concept))
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(Paper.id == paper_id, UserPaper.user_id == user_id)
    )
    if not paper:
        raise AppError("论文不存在", code="PAPER_NOT_FOUND", status_code=404)

    detail = PaperDetail.model_validate(paper)
    bookmark = await db.scalar(
        select(Bookmark).where(Bookmark.user_id == user_id, Bookmark.paper_id == paper_id)
    )
    detail.is_favorite = bookmark is not None

    # 关联概念：从 paper_concepts 表查询，按相关度排序
    active_run_id = paper.active_analysis_run_id
    concept_links = [
        link for link in paper.concepts
        if active_run_id is None or link.analysis_run_id == active_run_id
    ]
    concept_links.sort(key=lambda link: link.relevance, reverse=True)
    detail.related_concepts = [
        ConceptRef(
            id=link.concept.id,
            name=link.concept.name,
            description=link.concept.description,
            relevance=link.relevance,
        )
        for link in concept_links[:10]
    ]

    # 引用与关联论文：从 structured_content.references 提取 arXiv 链接
    refs = (paper.structured_content or {}).get("references", [])
    detail.related_papers = [
        PaperRef(
            id=ref.get("arxiv_id", ""),
            arxiv_id=ref.get("arxiv_id", ""),
            title=ref.get("title", ""),
            authors=ref.get("authors", []),
        )
        for ref in refs[:20]
        if ref.get("arxiv_id")
    ]

    return detail


async def get_paper_chunk(db: AsyncSession, user_id: UUID, paper_id: UUID, chunk_index: int) -> dict:
    chunk = await db.scalar(
        select(PaperChunk)
        .join(Paper, Paper.id == PaperChunk.paper_id)
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(
            PaperChunk.paper_id == paper_id,
            PaperChunk.chunk_index == chunk_index,
            UserPaper.user_id == user_id,
            or_(
                Paper.active_analysis_run_id.is_(None),
                PaperChunk.analysis_run_id == Paper.active_analysis_run_id,
            ),
        )
    )
    if chunk is None:
        raise AppError("论文原文片段不存在", code="PAPER_CHUNK_NOT_FOUND", status_code=404)
    return {
        "paperId": str(paper_id),
        "chunkIndex": chunk.chunk_index,
        "sectionTitle": chunk.section_title,
        "content": chunk.content,
    }


async def update_paper(
    db: AsyncSession,
    user_id: UUID,
    paper_id: UUID,
    changes: PaperUpdateRequest,
) -> PaperDetail:
    """Reject user attempts to mutate the shared paper cache.

    Parsed content is owned by the analysis pipeline. User-owned metadata
    belongs in UserPaper or another user-content table and must not be written
    to the global Paper row.
    """
    del db, user_id, paper_id, changes
    raise AppError("论文原始内容只能由内部分析任务更新", code="PAPER_CACHE_READ_ONLY", status_code=403)


async def delete_paper(db: AsyncSession, user_id: UUID, paper_id: UUID) -> None:
    """Remove a paper from one user's library without deleting cached content."""
    membership = await db.scalar(
        select(UserPaper).where(UserPaper.user_id == user_id, UserPaper.paper_id == paper_id)
    )
    if membership is None:
        raise AppError("论文不存在", code="PAPER_NOT_FOUND", status_code=404)
    await db.delete(membership)
    await db.commit()


async def delete_papers(db: AsyncSession, user_id: UUID, paper_ids: list[UUID]) -> list[UUID]:
    """Remove up to 100 papers from one user's library."""
    unique_ids = list(dict.fromkeys(paper_ids))
    memberships = (
        await db.scalars(
            select(UserPaper).where(UserPaper.user_id == user_id, UserPaper.paper_id.in_(unique_ids))
        )
    ).all()

    for membership in memberships:
        await db.delete(membership)
    await db.commit()
    return [membership.paper_id for membership in memberships]


async def add_paper_to_library(
    db: AsyncSession,
    user_id: UUID,
    paper_id: UUID,
) -> tuple[Paper, bool]:
    """Idempotently add a globally cached paper to one user's library."""
    paper = await db.get(Paper, paper_id)
    if paper is None:
        raise AppError("推荐论文不存在", code="PAPER_NOT_FOUND", status_code=404)

    membership = await db.scalar(
        select(UserPaper.id).where(UserPaper.user_id == user_id, UserPaper.paper_id == paper_id)
    )
    if membership is not None:
        return paper, False

    db.add(UserPaper(user_id=user_id, paper_id=paper_id))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        refreshed_paper = await db.get(Paper, paper_id)
        if refreshed_paper is None:
            raise AppError("推荐论文不存在", code="PAPER_NOT_FOUND", status_code=404)
        return refreshed_paper, False
    return paper, True


async def upsert_arxiv_papers(
    db: AsyncSession,
    raw_papers: list[dict],
) -> tuple[int, int]:
    """将 arXiv 拉取的论文批量插入或忽略（按 arxiv_id 去重）。

    Returns:
        (新插入数, 跳过数)
    """
    inserted = 0
    skipped = 0

    for raw in raw_papers:
        arxiv_id = raw["arxiv_id"]
        exists = await db.scalar(
            select(Paper).where(Paper.arxiv_id == arxiv_id).limit(1)
        )
        if exists:
            skipped += 1
            continue

        paper = Paper(
            arxiv_id=arxiv_id,
            title=raw["title"],
            authors=raw["authors"],
            abstract=raw["abstract"],
            categories=raw["categories"],
            primary_category=raw["primary_category"],
            published_at=raw.get("published_at"),
            updated_at_source=raw.get("updated_at_source"),
            pdf_url=raw.get("pdf_url", ""),
            arxiv_url=raw.get("arxiv_url", ""),
            parsed_status="pending",
            metadata_extra=raw.get("metadata_extra"),
        )
        db.add(paper)
        inserted += 1

    if inserted > 0:
        await db.commit()

    return inserted, skipped
