"""Business logic for trend analysis."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.paper import Paper
from app.models.task import TrendTopic


class TrendService:
    """Stateless service for research trend analysis."""

    async def get_trend_overview(self, db: AsyncSession) -> dict:
        """Aggregate trend signals and topic summaries."""
        trend_topics = (await db.scalars(select(TrendTopic))).all()

        now = datetime.now(timezone.utc)
        six_months_ago = now - timedelta(days=180)
        three_months_ago = now - timedelta(days=90)

        # ----- Signals: categories with rising paper counts -----
        categories = await db.execute(
            select(Paper.primary_category, func.count(Paper.id))
            .where(Paper.published_at >= six_months_ago)
            .group_by(Paper.primary_category)
            .order_by(func.count(Paper.id).desc())
            .limit(10)
        )
        cat_counts = {row[0]: row[1] for row in categories}

        prev_categories = await db.execute(
            select(Paper.primary_category, func.count(Paper.id))
            .where(
                Paper.published_at >= six_months_ago - timedelta(days=180),
                Paper.published_at < six_months_ago,
            )
            .group_by(Paper.primary_category)
        )
        prev_counts = {row[0]: row[1] for row in prev_categories}

        max_count = max(cat_counts.values()) if cat_counts else 1
        signals = []
        for cat, count in cat_counts.items():
            prev = prev_counts.get(cat, 0)
            mom_change = ((count - prev) / max(prev, 1)) * 100 if prev > 0 else 0
            signals.append({
                "name": cat,
                "hotness": min(100, int(count / max(max_count, 1) * 100)),
                "paper_count": count,
                "month_over_month_change": round(mom_change, 1),
            })

        # ----- Topic summaries -----
        topic_summaries = []
        for topic in trend_topics:
            paper_count = await self._count_matching_papers(db, topic.keywords)
            recent_count = await self._count_matching_papers(db, topic.keywords, since=three_months_ago)
            hotness = min(100, int(paper_count / max(max_count, 1) * 100)) if paper_count > 0 else 0

            # Detect direction
            earlier_count = paper_count - recent_count
            if recent_count > earlier_count * 1.2:
                direction = "rising"
            elif recent_count < earlier_count * 0.8 and paper_count > 0:
                direction = "declining"
            else:
                direction = "stable"

            topic_summaries.append({
                "id": str(topic.id),
                "name": topic.name,
                "description": topic.description,
                "keywords": topic.keywords or [],
                "paper_count": paper_count,
                "hotness": hotness,
                "trend_direction": direction,
            })

        return {"signals": signals, "topics": topic_summaries}

    async def get_trend_detail(self, db: AsyncSession, topic_id: UUID) -> dict:
        """Get detailed trend data for a specific topic."""
        topic = await db.get(TrendTopic, topic_id)
        if topic is None:
            raise ValueError("Trend topic not found")

        # Monthly paper count for last 24 months
        now = datetime.now(timezone.utc)
        months: list[str] = []
        monthly_data: list[dict] = []
        for i in range(23, -1, -1):
            start = now - timedelta(days=(i + 1) * 30)
            end = now - timedelta(days=i * 30)
            month_label = start.strftime("%Y-%m")
            months.append(month_label)
            count = await self._count_matching_papers(db, topic.keywords, since=start, until=end)
            monthly_data.append({"month": month_label, "count": count})

        # Milestone papers
        milestones = await self._identify_milestones(db, topic.keywords)

        # Phase analysis
        phases = self._detect_phases(monthly_data)

        return {
            "id": str(topic.id),
            "name": topic.name,
            "description": topic.description,
            "keywords": topic.keywords or [],
            "monthly_trend": monthly_data,
            "milestones": milestones,
            "phases": phases,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    async def _count_matching_papers(
        self, db: AsyncSession, keywords: list[str],
        since: datetime | None = None, until: datetime | None = None,
    ) -> int:
        if not keywords:
            return 0
        stmt = select(func.count(Paper.id))
        # Match any keyword against title or abstract
        conditions = []
        for kw in keywords:
            conditions.append(Paper.title.ilike(f"%{kw}%"))
            conditions.append(Paper.abstract.ilike(f"%{kw}%"))
        from sqlalchemy import or_
        stmt = stmt.where(or_(*conditions))
        if since:
            stmt = stmt.where(Paper.published_at >= since)
        if until:
            stmt = stmt.where(Paper.published_at < until)
        count = await db.scalar(stmt)
        return count or 0

    async def _identify_milestones(self, db: AsyncSession, keywords: list[str]) -> list[dict]:
        """Identify key milestone papers for a research topic."""
        if not keywords:
            return []
        from sqlalchemy import or_
        stmt = (
            select(Paper)
            .where(or_(*[Paper.title.ilike(f"%{kw}%") for kw in keywords]))
            .order_by(Paper.published_at.asc())
            .limit(10)
        )
        papers = (await db.scalars(stmt)).all()

        milestones = []
        for i, p in enumerate(papers):
            if i == 0:
                sig = "first_of_kind"
            elif i == len(papers) - 1:
                sig = "most_recent"
            else:
                sig = "turning_point"
            milestones.append({
                "paper_id": str(p.id),
                "title": p.title,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "citation_count": 0,  # requires PaperCitation data populated
                "significance": sig,
            })
        return milestones

    def _detect_phases(self, monthly_data: list[dict]) -> list[dict]:
        """Detect emerging / growing / mature / declining phases from monthly trend."""
        if len(monthly_data) < 6:
            return []

        counts = [d["count"] for d in monthly_data]
        months = [d["month"] for d in monthly_data]
        total = sum(counts)
        if total == 0:
            return [{
                "phase": "emerging", "start_month": months[0],
                "end_month": months[-1], "description": "该主题暂无显著论文数据，处于萌芽阶段"
            }]

        # Simple heuristic: sliding window detection
        phases = []
        window = 6
        for i in range(0, len(counts) - window + 1, window):
            seg = counts[i : i + window]
            avg = sum(seg) / window
            if avg == 0:
                continue
            first_half = sum(seg[:3])
            second_half = sum(seg[3:])
            if first_half > 0 and second_half > first_half * 1.2:
                phase = "growing"
                desc = "论文数量持续增长"
            elif first_half > second_half * 1.3:
                phase = "declining"
                desc = "论文热度逐渐下降"
            elif avg > sum(counts) / len(counts):
                phase = "mature"
                desc = "研究进入成熟期，产出稳定"
            else:
                phase = "emerging"
                desc = "新兴研究领域，关注度上升"
            phases.append({
                "phase": phase,
                "start_month": months[i],
                "end_month": months[min(i + window - 1, len(months) - 1)],
                "description": desc,
            })

        if not phases:
            phases.append({
                "phase": "emerging", "start_month": months[0],
                "end_month": months[-1], "description": "该主题处于发展初期"
            })
        return phases


trend_service = TrendService()
