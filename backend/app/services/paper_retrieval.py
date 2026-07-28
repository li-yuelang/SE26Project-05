"""Paper-level hybrid retrieval for subscriptions and recommendations."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.embedding import get_embedding_provider
from app.models.paper import Paper, PaperChunk

logger = logging.getLogger(__name__)


@dataclass
class PaperRetrievalResult:
    paper: Paper
    score: float
    lexical_score: float
    semantic_score: float | None
    freshness_score: float
    matched_terms: list[str]
    reason: str


def calculate_lexical_relevance(
    paper: object,
    terms: list[str],
) -> tuple[float, list[str]]:
    """Score keyword coverage in title, abstract and arXiv categories."""
    normalized_terms = list(
        dict.fromkeys(term.strip().lower() for term in terms if term.strip())
    )
    if not normalized_terms:
        return 0.0, []

    title = (getattr(paper, "title", "") or "").lower()
    abstract = (getattr(paper, "abstract", "") or "").lower()
    categories = [getattr(paper, "primary_category", "") or ""]
    categories.extend(getattr(paper, "categories", None) or [])
    category_text = " ".join(categories).lower()

    matched: list[str] = []
    title_hits = 0
    category_hits = 0
    for term in normalized_terms:
        in_title = term in title
        in_abstract = term in abstract
        in_category = term in category_text
        if in_title or in_abstract or in_category:
            matched.append(term)
        title_hits += int(in_title)
        category_hits += int(in_category)

    term_count = len(normalized_terms)
    coverage = len(matched) / term_count
    title_ratio = title_hits / term_count
    category_ratio = category_hits / term_count
    score = 0.5 * coverage + 0.35 * title_ratio + 0.15 * category_ratio
    return round(min(score, 1.0), 4), matched


def calculate_hybrid_score(
    lexical_score: float,
    semantic_score: float | None,
    freshness_score: float,
) -> float:
    """Fuse comparable [0, 1] scores and renormalize when vectors are absent."""
    if semantic_score is None:
        return round(0.8 * lexical_score + 0.2 * freshness_score, 4)
    return round(
        0.4 * lexical_score + 0.5 * semantic_score + 0.1 * freshness_score,
        4,
    )


class PaperHybridRetriever:
    """Retrieve global papers using lexical, metadata and chunk-vector signals."""

    async def embed_queries(self, queries: list[str]) -> list[list[float] | None]:
        cleaned = [query.strip() for query in queries]
        if not cleaned:
            return []
        embedding_configured = bool(
            settings.embedding_api_key
            or (settings.embedding_base_url and settings.llm_api_key)
        )
        if not embedding_configured:
            return [None] * len(cleaned)
        nonempty_indexes = [index for index, query in enumerate(cleaned) if query]
        if not nonempty_indexes:
            return [None] * len(cleaned)
        try:
            vectors = await get_embedding_provider().embed(
                [cleaned[index] for index in nonempty_indexes]
            )
        except Exception:
            logger.warning(
                "Semantic paper retrieval unavailable; using lexical fallback",
                exc_info=True,
            )
            return [None] * len(cleaned)

        results: list[list[float] | None] = [None] * len(cleaned)
        for index, vector in zip(nonempty_indexes, vectors, strict=True):
            results[index] = vector
        return results

    async def search(
        self,
        db: AsyncSession,
        *,
        terms: list[str],
        categories: list[str],
        query_embedding: list[float] | None,
        since: datetime | None = None,
        exclude_ids: set[UUID] | None = None,
        candidate_limit: int = 80,
        result_limit: int = 10,
        reason_prefix: str = "",
    ) -> list[PaperRetrievalResult]:
        exclude_ids = exclude_ids or set()
        lexical_ids = await self._lexical_candidates(
            db,
            terms=terms,
            categories=categories,
            since=since,
            exclude_ids=exclude_ids,
            limit=candidate_limit,
        )
        semantic_distances = await self._semantic_candidates(
            db,
            query_embedding=query_embedding,
            since=since,
            exclude_ids=exclude_ids,
            limit=candidate_limit,
        )
        candidate_ids = set(lexical_ids) | set(semantic_distances)
        if not candidate_ids:
            return []

        papers = list(
            (await db.scalars(select(Paper).where(Paper.id.in_(candidate_ids)))).all()
        )
        all_terms = [*terms, *categories]
        now = datetime.now(timezone.utc)
        horizon_days = max(1, (now - since).days) if since else 365
        results = []
        for paper in papers:
            lexical_score, matched_terms = calculate_lexical_relevance(
                paper,
                all_terms,
            )
            distance = semantic_distances.get(paper.id)
            semantic_score = (
                max(0.0, min(1.0, 1.0 - float(distance)))
                if distance is not None
                else None
            )
            age_days = max(
                0.0,
                (now - paper.published_at).total_seconds() / 86400,
            )
            freshness_score = max(0.0, 1.0 - age_days / horizon_days)
            score = calculate_hybrid_score(
                lexical_score,
                semantic_score,
                freshness_score,
            )
            results.append(
                PaperRetrievalResult(
                    paper=paper,
                    score=score,
                    lexical_score=lexical_score,
                    semantic_score=semantic_score,
                    freshness_score=freshness_score,
                    matched_terms=matched_terms,
                    reason=self._build_reason(
                        matched_terms,
                        semantic_score,
                        reason_prefix,
                    ),
                )
            )

        results.sort(
            key=lambda item: (item.score, item.paper.published_at),
            reverse=True,
        )
        return results[:result_limit]

    @staticmethod
    async def _lexical_candidates(
        db: AsyncSession,
        *,
        terms: list[str],
        categories: list[str],
        since: datetime | None,
        exclude_ids: set[UUID],
        limit: int,
    ) -> list[UUID]:
        conditions = []
        for term in terms:
            cleaned = term.strip()
            if not cleaned:
                continue
            conditions.extend(
                (
                    Paper.title.ilike(f"%{cleaned}%"),
                    Paper.abstract.ilike(f"%{cleaned}%"),
                )
            )
        for category in categories:
            cleaned = category.strip()
            if not cleaned:
                continue
            conditions.extend(
                (
                    Paper.primary_category == cleaned,
                    Paper.categories.contains([cleaned]),
                )
            )
        if not conditions:
            return []

        statement = select(Paper.id).where(or_(*conditions))
        if since:
            statement = statement.where(Paper.published_at >= since)
        if exclude_ids:
            statement = statement.where(Paper.id.not_in(exclude_ids))
        statement = statement.order_by(Paper.published_at.desc()).limit(limit)
        return list((await db.scalars(statement)).all())

    @staticmethod
    async def _semantic_candidates(
        db: AsyncSession,
        *,
        query_embedding: list[float] | None,
        since: datetime | None,
        exclude_ids: set[UUID],
        limit: int,
    ) -> dict[UUID, float]:
        if query_embedding is None:
            return {}

        abstract_distance = Paper.abstract_embedding.cosine_distance(query_embedding)
        abstract_statement = select(
            Paper.id,
            abstract_distance.label("best_distance"),
        ).where(Paper.abstract_embedding.is_not(None))
        if since:
            abstract_statement = abstract_statement.where(Paper.published_at >= since)
        if exclude_ids:
            abstract_statement = abstract_statement.where(Paper.id.not_in(exclude_ids))
        abstract_statement = abstract_statement.order_by(abstract_distance).limit(limit)
        abstract_rows = (await db.execute(abstract_statement)).all()

        chunk_distance = PaperChunk.embedding.cosine_distance(query_embedding)
        best_chunk_distance = func.min(chunk_distance).label("best_distance")
        chunk_statement = (
            select(PaperChunk.paper_id, best_chunk_distance)
            .join(Paper, Paper.id == PaperChunk.paper_id)
            .where(
                PaperChunk.embedding.is_not(None),
                or_(
                    Paper.active_analysis_run_id.is_(None),
                    PaperChunk.analysis_run_id == Paper.active_analysis_run_id,
                ),
            )
            .group_by(PaperChunk.paper_id)
            .order_by(best_chunk_distance)
            .limit(limit)
        )
        if since:
            chunk_statement = chunk_statement.where(Paper.published_at >= since)
        if exclude_ids:
            chunk_statement = chunk_statement.where(PaperChunk.paper_id.not_in(exclude_ids))
        chunk_rows = (await db.execute(chunk_statement)).all()

        distances = {
            paper_id: float(candidate_distance)
            for paper_id, candidate_distance in abstract_rows
        }
        for paper_id, candidate_distance in chunk_rows:
            numeric_distance = float(candidate_distance)
            distances[paper_id] = min(
                distances.get(paper_id, numeric_distance),
                numeric_distance,
            )
        return distances

    @staticmethod
    def _build_reason(
        matched_terms: list[str],
        semantic_score: float | None,
        prefix: str,
    ) -> str:
        reasons = [prefix] if prefix else []
        if matched_terms:
            reasons.append(f"命中主题条件：{'、'.join(matched_terms[:3])}")
        if semantic_score is not None and semantic_score >= 0.45:
            reasons.append("论文内容与主题语义相似")
        reasons.append("结合发布时间排序")
        return "；".join(reasons)


paper_hybrid_retriever = PaperHybridRetriever()
