"""Daily arXiv ingestion for subscription digests."""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedding import get_embedding_provider
from app.models.paper import Paper
from app.models.task import Subscription
from app.services.arxiv_fetch import build_search_query, fetch_arxiv_window

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SubscriptionArxivQuery:
    keywords: tuple[str, ...]
    categories: tuple[str, ...]


@dataclass
class DigestSyncStats:
    status: str = "succeeded"
    query_count: int = 0
    candidate_count: int = 0
    unique_candidate_count: int = 0
    inserted_count: int = 0
    updated_count: int = 0
    duplicate_count: int = 0
    embedding_count: int = 0
    embedding_failed_count: int = 0

    def to_dict(self) -> dict[str, str | int]:
        return asdict(self)


def _normalise_values(values: Iterable[str]) -> tuple[str, ...]:
    normalised: dict[str, str] = {}
    for value in values:
        cleaned = str(value).strip()
        if cleaned:
            normalised.setdefault(cleaned.casefold(), cleaned)
    return tuple(sorted(normalised.values(), key=str.casefold))


def unique_subscription_queries(
    subscriptions: Iterable[Subscription],
) -> list[SubscriptionArxivQuery]:
    queries_by_key: dict[
        tuple[tuple[str, ...], tuple[str, ...]],
        SubscriptionArxivQuery,
    ] = {}
    for subscription in subscriptions:
        if not subscription.enabled:
            continue
        query = SubscriptionArxivQuery(
            keywords=_normalise_values(subscription.topic_keywords or []),
            categories=_normalise_values(subscription.categories or []),
        )
        if not query.keywords and not query.categories:
            continue
        key = (
            tuple(value.casefold() for value in query.keywords),
            tuple(value.casefold() for value in query.categories),
        )
        queries_by_key.setdefault(key, query)
    return sorted(
        queries_by_key.values(),
        key=lambda item: (
            tuple(value.casefold() for value in item.keywords),
            tuple(value.casefold() for value in item.categories),
        ),
    )


def _source_values(raw: dict) -> dict:
    return {
        "title": raw.get("title") or raw["arxiv_id"],
        "authors": raw.get("authors") or [],
        "abstract": raw.get("abstract") or "",
        "categories": raw.get("categories") or [],
        "primary_category": raw.get("primary_category"),
        "published_at": raw["published_at"],
        "updated_at_source": raw.get("updated_at_source"),
        "pdf_url": raw.get("pdf_url") or "",
        "arxiv_url": raw.get("arxiv_url") or "",
        "metadata_extra": raw.get("metadata_extra"),
    }


async def _persist_candidates(
    db: AsyncSession,
    candidates: list[dict],
) -> tuple[int, int, int, list[Paper]]:
    arxiv_ids = [str(candidate["arxiv_id"]).strip() for candidate in candidates]
    existing_papers = (
        list(
            (
                await db.scalars(
                    select(Paper).where(Paper.arxiv_id.in_(arxiv_ids))
                )
            ).all()
        )
        if arxiv_ids
        else []
    )
    existing_by_id = {paper.arxiv_id: paper for paper in existing_papers}
    inserted_count = 0
    updated_count = 0
    duplicate_count = 0
    embedding_targets: list[Paper] = []

    for raw in candidates:
        arxiv_id = str(raw["arxiv_id"]).strip()
        source_values = _source_values(raw)
        paper = existing_by_id.get(arxiv_id)
        if paper is None:
            paper = Paper(arxiv_id=arxiv_id, parsed_status="pending", **source_values)
            db.add(paper)
            existing_by_id[arxiv_id] = paper
            inserted_count += 1
            embedding_targets.append(paper)
            continue

        semantic_text_changed = (
            paper.title != source_values["title"]
            or paper.abstract != source_values["abstract"]
        )
        changed = False
        for field, value in source_values.items():
            if getattr(paper, field) != value:
                setattr(paper, field, value)
                changed = True
        if changed:
            updated_count += 1
        else:
            duplicate_count += 1
        if semantic_text_changed or paper.abstract_embedding is None:
            embedding_targets.append(paper)

    await db.commit()
    return inserted_count, updated_count, duplicate_count, embedding_targets


async def _embed_papers(db: AsyncSession, papers: list[Paper]) -> tuple[int, int]:
    if not papers:
        return 0, 0
    texts = [f"{paper.title}\n\n{paper.abstract}".strip() for paper in papers]
    try:
        embeddings = await get_embedding_provider().embed(texts)
        for paper, embedding in zip(papers, embeddings, strict=True):
            paper.abstract_embedding = embedding
        await db.commit()
        return len(embeddings), 0
    except Exception:
        await db.rollback()
        logger.warning(
            "Unable to generate digest abstract embeddings; lexical fallback will be used",
            exc_info=True,
        )
        return 0, len(papers)


async def sync_subscription_arxiv(
    db: AsyncSession,
    *,
    now: datetime | None = None,
) -> dict[str, str | int]:
    """Fetch the last arXiv window for all unique enabled subscription queries."""

    current_time = now or datetime.now(timezone.utc)
    window_start = current_time - timedelta(hours=settings.digest_arxiv_lookback_hours)
    subscriptions = list(
        (
            await db.scalars(
                select(Subscription).where(Subscription.enabled.is_(True))
            )
        ).all()
    )
    queries = unique_subscription_queries(subscriptions)
    stats = DigestSyncStats(query_count=len(queries))
    candidates_by_id: dict[str, dict] = {}

    for subscription_query in queries:
        query = build_search_query(
            keywords=list(subscription_query.keywords),
            categories=list(subscription_query.categories),
            keyword_match_mode="or",
        )
        candidates, _ = await fetch_arxiv_window(
            query,
            window_start=window_start,
            window_end=current_time,
            max_results=settings.digest_arxiv_max_results_per_subscription,
        )
        stats.candidate_count += len(candidates)
        for candidate in candidates:
            arxiv_id = str(candidate.get("arxiv_id", "")).strip()
            if arxiv_id:
                candidates_by_id[arxiv_id] = candidate

    candidates = list(candidates_by_id.values())
    stats.unique_candidate_count = len(candidates)
    (
        stats.inserted_count,
        stats.updated_count,
        stats.duplicate_count,
        embedding_targets,
    ) = await _persist_candidates(db, candidates)
    stats.embedding_count, stats.embedding_failed_count = await _embed_papers(
        db,
        embedding_targets,
    )
    if stats.embedding_failed_count:
        stats.status = "succeeded_with_warnings"

    logger.info("Daily arXiv subscription sync completed: %s", stats.to_dict())
    return stats.to_dict()


__all__ = [
    "DigestSyncStats",
    "SubscriptionArxivQuery",
    "sync_subscription_arxiv",
    "unique_subscription_queries",
]
