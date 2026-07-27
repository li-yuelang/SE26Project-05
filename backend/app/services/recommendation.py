"""Business logic for recommendations."""
from __future__ import annotations


from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import Bookmark
from app.models.concept import PaperConcept
from app.models.paper import Paper, UserPaper
from app.models.user import User


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
        for items in result.values():
            for item in items:
                item["in_library"] = item["paper_id"] in library_ids
        return result

    async def _recommend_by_content(self, db: AsyncSession, user: User) -> list[dict]:
        """Content-based recommendation using bookmarked paper concepts."""
        bookmarked_papers = (await db.scalars(
            select(Bookmark.paper_id).where(Bookmark.user_id == user.id)
        )).all()

        if not bookmarked_papers:
            return []

        # Get concepts from bookmarked papers
        pc_rows = (await db.scalars(
            select(PaperConcept.concept_id)
            .join(Paper, Paper.id == PaperConcept.paper_id)
            .where(PaperConcept.paper_id.in_(bookmarked_papers))
            .where(
                or_(
                    Paper.active_analysis_run_id.is_(None),
                    PaperConcept.analysis_run_id == Paper.active_analysis_run_id,
                )
            )
        )).all()
        concept_ids = list(set(pc_rows))

        if not concept_ids:
            return []

        # Find papers sharing those concepts, excluding already bookmarked ones
        candidate_paper_ids = (await db.scalars(
            select(PaperConcept.paper_id)
            .join(Paper, Paper.id == PaperConcept.paper_id)
            .where(
                PaperConcept.concept_id.in_(concept_ids),
                PaperConcept.paper_id.not_in(bookmarked_papers),
                or_(
                    Paper.active_analysis_run_id.is_(None),
                    PaperConcept.analysis_run_id == Paper.active_analysis_run_id,
                ),
            )
            .group_by(PaperConcept.paper_id)
            .order_by(func.count(PaperConcept.concept_id).desc())
            .limit(10)
        )).all()

        if not candidate_paper_ids:
            return []

        papers = (await db.scalars(select(Paper).where(Paper.id.in_(candidate_paper_ids)))).all()
        return [
            self._serialise_recommendation(p, 0.75, "基于你收藏论文的概念关联推荐")
            for p in papers
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
