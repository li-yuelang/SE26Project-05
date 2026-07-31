"""Business logic for recommendations."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import Bookmark
from app.models.paper import Paper, UserPaper
from app.models.task import Subscription
from app.models.user import User
from app.services.paper_retrieval import paper_hybrid_retriever


class RecommendationService:
    """Stateless service for content-based and collaborative recommendations."""

    async def get_recommendations(self, db: AsyncSession, user: User) -> dict:
        content_based = await self._recommend_by_content(db, user)
        collaborative = await self._recommend_collaborative(db, user)
        result = {
            "content_based": content_based,
            "collaborative": collaborative,
        }
        library_ids = {
            str(paper_id)
            for paper_id in (
                await db.scalars(
                    select(UserPaper.paper_id).where(UserPaper.user_id == user.id)
                )
            ).all()
        }
        seen_paper_ids: set[str] = set()
        for items in result.values():
            unique_items = []
            for item in items:
                if item["paper_id"] in seen_paper_ids:
                    continue
                seen_paper_ids.add(item["paper_id"])
                item["in_library"] = item["paper_id"] in library_ids
                unique_items.append(item)
            items[:] = unique_items
        return result

    async def _recommend_by_content(self, db: AsyncSession, user: User) -> list[dict]:
        """Recommend with bookmark semantics and subscription metadata."""
        bookmarked_ids = list((await db.scalars(
            select(Bookmark.paper_id).where(Bookmark.user_id == user.id)
        )).all())
        bookmarked_papers = (
            list(
                (
                    await db.scalars(
                        select(Paper).where(Paper.id.in_(bookmarked_ids))
                    )
                ).all()
            )
            if bookmarked_ids
            else []
        )
        subscriptions = list(
            (
                await db.scalars(
                    select(Subscription).where(
                        Subscription.user_id == user.id,
                        Subscription.enabled.is_(True),
                    )
                )
            ).all()
        )

        terms = list(
            dict.fromkeys(
                keyword.strip()
                for subscription in subscriptions
                for keyword in (subscription.topic_keywords or [])
                if keyword.strip()
            )
        )
        categories = list(
            dict.fromkeys(
                [
                    *(
                        category.strip()
                        for subscription in subscriptions
                        for category in (subscription.categories or [])
                        if category.strip()
                    ),
                    *(
                        paper.primary_category
                        for paper in bookmarked_papers
                        if paper.primary_category
                    ),
                ]
            )
        )
        if not bookmarked_papers and not terms and not categories:
            return []

        profile_parts = [
            f"{paper.title}. {(paper.abstract or '')[:500]}"
            for paper in bookmarked_papers[:5]
        ]
        if terms:
            profile_parts.append("Subscribed topics: " + ", ".join(terms))
        query_embedding = (
            await paper_hybrid_retriever.embed_queries(["\n".join(profile_parts)])
        )[0]
        library_ids = set(
            (
                await db.scalars(
                    select(UserPaper.paper_id).where(UserPaper.user_id == user.id)
                )
            ).all()
        )
        recommendations = await paper_hybrid_retriever.search(
            db,
            terms=terms,
            categories=categories,
            query_embedding=query_embedding,
            since=datetime.now(timezone.utc) - timedelta(days=730),
            exclude_ids=library_ids,
            result_limit=10,
            reason_prefix="基于你的收藏论文与订阅主题",
        )
        return [
            self._serialise_recommendation(item.paper, item.score, item.reason)
            for item in recommendations
        ]

    async def _recommend_collaborative(self, db: AsyncSession, user: User) -> list[dict]:
        """Simple collaborative filtering: papers read by users with similar reading patterns."""
        # Get users who bookmarked the same papers as current user
        my_bookmarks = (await db.scalars(
            select(Bookmark.paper_id).where(Bookmark.user_id == user.id)
        )).all()

        if not my_bookmarks:
            return []

        # Find similar users
        similar_users = (await db.execute(
            select(Bookmark.user_id, func.count(Bookmark.paper_id).label("common"))
            .where(Bookmark.paper_id.in_(my_bookmarks), Bookmark.user_id != user.id)
            .group_by(Bookmark.user_id)
            .order_by(func.count(Bookmark.paper_id).desc())
            .limit(10)
        )).all()

        if not similar_users:
            return []

        similar_user_ids = [row[0] for row in similar_users]

        # Papers bookmarked by similar users but not by current user
        candidate_ids = (await db.scalars(
            select(Bookmark.paper_id)
            .where(
                Bookmark.user_id.in_(similar_user_ids),
                Bookmark.paper_id.not_in(my_bookmarks),
            )
            .group_by(Bookmark.paper_id)
            .order_by(func.count(Bookmark.paper_id).desc())
            .limit(10)
        )).all()

        if not candidate_ids:
            return []

        papers = (await db.scalars(select(Paper).where(Paper.id.in_(candidate_ids)))).all()
        return [
            self._serialise_recommendation(p, 0.7, "同领域研究者也在收藏")
            for p in papers
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _serialise_recommendation(paper: Paper, score: float, reason: str) -> dict:
        return {
            "paper_id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "arxiv_url": getattr(paper, "arxiv_url", None)
            or f"https://arxiv.org/abs/{paper.arxiv_id}",
            "title": paper.title,
            "authors": paper.authors or [],
            "abstract": paper.abstract or "",
            "primary_category": paper.primary_category or "",
            "relevance_score": score,
            "reason": reason,
        }


recommendation_service = RecommendationService()
