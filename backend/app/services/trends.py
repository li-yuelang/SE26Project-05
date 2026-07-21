"""Business logic for research-roadmap and trend analysis."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.concept import Concept, ConceptRelation, PaperConcept
from app.models.paper import PaperCitation, UserPaper


def _shift_month(value: datetime, offset: int) -> datetime:
    month_index = value.year * 12 + value.month - 1 + offset
    return datetime(month_index // 12, month_index % 12 + 1, 1, tzinfo=timezone.utc)


class TrendService:
    """Build trend views from concepts extracted from papers in a user's library."""

    async def get_trend_overview(self, db: AsyncSession, user_id: UUID) -> dict:
        library_ids = await self._library_paper_ids(db, user_id)
        concepts = await self._load_concepts(db, library_ids)
        concepts = [item for item in concepts if self._paper_links(item, library_ids)]
        if not concepts:
            return self._empty_overview()

        paper_counts = [len(self._paper_links(concept, library_ids)) for concept in concepts]
        max_count = max(paper_counts, default=1)
        topics = [
            self._topic_view(concept, library_ids, max_count=max_count)
            for concept in concepts
        ]
        topics.sort(key=lambda topic: (topic["hotness"], topic["paper_count"]), reverse=True)

        related = {
            str(concept.id): self._relation_views(concept, {str(item.id) for item in concepts})
            for concept in concepts
        }
        signals = [self._signal_view(topic) for topic in topics[:6]]
        categories = sorted({topic["category"] for topic in topics if topic["category"]})
        return {
            "topics": topics,
            "signals": signals,
            "related_concepts_by_topic_id": related,
            "category_options": ["全部", *categories],
        }

    async def get_trend_detail(
        self,
        db: AsyncSession,
        topic_id: UUID,
        user_id: UUID,
    ) -> dict:
        library_ids = await self._library_paper_ids(db, user_id)
        concepts = await self._load_concepts(db, library_ids)
        concepts = [item for item in concepts if self._paper_links(item, library_ids)]
        concept = next((item for item in concepts if item.id == topic_id), None)
        if concept is None:
            raise ValueError("Trend topic not found")

        max_count = max(
            (len(self._paper_links(item, library_ids)) for item in concepts),
            default=1,
        )
        topics = [self._topic_view(item, library_ids, max_count=max_count) for item in concepts]
        topics.sort(key=lambda topic: (topic["hotness"], topic["paper_count"]), reverse=True)
        topic = next(item for item in topics if item["id"] == str(topic_id))

        links = self._paper_links(concept, library_ids)
        paper_ids = [link.paper.id for link in links]
        citation_counts = await self._citation_counts(db, paper_ids)
        representative_papers = [
            self._paper_view(link, citation_counts.get(link.paper.id, 0))
            for link in links
        ]
        representative_papers.sort(
            key=lambda paper: (
                paper["citation_count"],
                paper["relevance"],
                paper["published_at"] or "",
            ),
            reverse=True,
        )

        phases = self._detect_phases(topic["monthly_trend"])
        relations = self._relation_views(concept, {item["id"] for item in topics})
        return {
            "topic": {**topic, "representative_papers": representative_papers[:10]},
            "topics": topics,
            "topic_rank": next(
                index for index, item in enumerate(topics, start=1) if item["id"] == str(topic_id)
            ),
            "monthly_trend": topic["monthly_trend"],
            "representative_papers": representative_papers[:10],
            "milestones": self._milestones(representative_papers),
            "phases": phases,
            "related_concepts": relations,
            "signals": [self._signal_view(topic)],
        }

    async def _library_paper_ids(self, db: AsyncSession, user_id: UUID) -> set[UUID]:
        return set(
            (
                await db.scalars(
                    select(UserPaper.paper_id).where(UserPaper.user_id == user_id)
                )
            ).all()
        )

    async def _load_concepts(
        self,
        db: AsyncSession,
        library_ids: set[UUID],
    ) -> list[Concept]:
        if not library_ids:
            return []
        statement = (
            select(Concept)
            .join(PaperConcept, PaperConcept.concept_id == Concept.id)
            .where(PaperConcept.paper_id.in_(library_ids))
            .options(
                selectinload(Concept.paper_links).selectinload(PaperConcept.paper),
                selectinload(Concept.outgoing_relations).selectinload(
                    ConceptRelation.target_concept
                ),
                selectinload(Concept.incoming_relations).selectinload(
                    ConceptRelation.source_concept
                ),
            )
            .order_by(Concept.updated_at.desc(), Concept.name)
        )
        return list((await db.scalars(statement)).unique().all())

    @staticmethod
    def _paper_links(concept: Concept, library_ids: set[UUID]) -> list[PaperConcept]:
        unique_links: dict[UUID, PaperConcept] = {}
        for link in concept.paper_links:
            paper = link.paper
            if paper.id not in library_ids:
                continue
            if (
                paper.active_analysis_run_id
                and link.analysis_run_id != paper.active_analysis_run_id
            ):
                continue
            current = unique_links.get(paper.id)
            if current is None or link.relevance > current.relevance:
                unique_links[paper.id] = link
        return list(unique_links.values())

    def _topic_view(
        self,
        concept: Concept,
        library_ids: set[UUID],
        *,
        max_count: int,
    ) -> dict:
        links = self._paper_links(concept, library_ids)
        papers = [link.paper for link in links]
        monthly_trend = self._monthly_counts(papers, months=24)
        counts = [point["count"] for point in monthly_trend]
        recent = sum(counts[-3:])
        previous = sum(counts[-6:-3])
        momentum = round((recent - previous) / max(previous, 1) * 100)
        momentum = max(-100, min(100, momentum))
        if recent > previous * 1.2 and recent > 0:
            direction = "rising"
        elif previous > recent * 1.2 and previous > 0:
            direction = "declining"
        else:
            direction = "stable"

        recent_share = recent / max(len(papers), 1)
        hotness = min(100, round(70 * len(papers) / max(max_count, 1) + 30 * recent_share))
        description = concept.description or "暂无主题说明"
        summary_points = [
            sentence.strip()
            for sentence in re.split(r"[。！？\n]+", description)
            if sentence.strip()
        ][:3] or [description]
        lightweight_papers = [self._paper_view(link, 0) for link in links]
        lightweight_papers.sort(key=lambda item: item["published_at"] or "", reverse=True)
        return {
            "id": str(concept.id),
            "name": concept.name,
            "category": concept.category or "未分类",
            "description": description,
            "aliases": concept.aliases or [],
            "keywords": concept.aliases or [concept.name],
            "mentions": len(links),
            "paper_count": len(links),
            "hotness": hotness,
            "momentum": momentum,
            "trend_direction": direction,
            "updated_at": concept.updated_at.date().isoformat(),
            "monthly_trend": monthly_trend,
            "summary_points": summary_points,
            "representative_papers": lightweight_papers[:5],
        }

    @staticmethod
    def _monthly_counts(papers: list[object], *, months: int) -> list[dict]:
        now = datetime.now(timezone.utc)
        current_month = datetime(now.year, now.month, 1, tzinfo=timezone.utc)
        starts = [_shift_month(current_month, offset) for offset in range(-(months - 1), 1)]
        counts = {start.strftime("%Y-%m"): 0 for start in starts}
        for paper in papers:
            published_at = getattr(paper, "published_at", None)
            if published_at is None:
                continue
            label = published_at.strftime("%Y-%m")
            if label in counts:
                counts[label] += 1
        return [{"month": month, "count": count} for month, count in counts.items()]

    async def _citation_counts(
        self,
        db: AsyncSession,
        paper_ids: list[UUID],
    ) -> dict[UUID, int]:
        if not paper_ids:
            return {}
        rows = await db.execute(
            select(PaperCitation.target_paper_id, func.count(PaperCitation.id))
            .where(PaperCitation.target_paper_id.in_(paper_ids))
            .group_by(PaperCitation.target_paper_id)
        )
        return {paper_id: count for paper_id, count in rows}

    @staticmethod
    def _paper_view(link: PaperConcept, citation_count: int) -> dict:
        paper = link.paper
        return {
            "paper_id": str(paper.id),
            "arxiv_id": paper.arxiv_id,
            "arxiv_url": paper.arxiv_url,
            "title": paper.title,
            "year": paper.published_at.year if paper.published_at else None,
            "published_at": paper.published_at.isoformat() if paper.published_at else None,
            "role": link.evidence or "该主题的代表性研究",
            "relevance": round(link.relevance * 100),
            "citation_count": citation_count,
        }

    @staticmethod
    def _milestones(papers: list[dict]) -> list[dict]:
        chronological = sorted(papers, key=lambda paper: paper["published_at"] or "")
        if len(chronological) > 8:
            indexes = {
                round(index * (len(chronological) - 1) / 7)
                for index in range(8)
            }
            chronological = [
                paper
                for index, paper in enumerate(chronological)
                if index in indexes
            ]
        milestones = []
        for index, paper in enumerate(chronological):
            if index == 0:
                significance = "foundation"
            elif index == len(chronological) - 1:
                significance = "frontier"
            elif paper["citation_count"] > 0:
                significance = "representative"
            else:
                significance = "development"
            milestones.append({**paper, "significance": significance})
        return milestones

    @staticmethod
    def _relation_views(concept: Concept, available_ids: set[str]) -> list[dict]:
        relations = []
        for relation in [*concept.outgoing_relations, *concept.incoming_relations]:
            target = (
                relation.target_concept
                if relation.source_concept_id == concept.id
                else relation.source_concept
            )
            relations.append({
                "id": str(relation.id),
                "type": relation.relation_type,
                "strength": round(relation.weight * 100),
                "exists": str(target.id) in available_ids,
                "concept": {"id": str(target.id), "name": target.name},
            })
        return relations

    @staticmethod
    def _signal_view(topic: dict) -> dict:
        direction_text = {
            "rising": "论文数量正在上升",
            "declining": "近期论文数量有所下降",
            "stable": "论文数量保持稳定",
        }[topic["trend_direction"]]
        return {
            "id": f"trend-{topic['id']}",
            "title": f"{topic['name']}：{direction_text}",
            "description": (
                f"当前收录 {topic['paper_count']} 篇相关论文，"
                f"近三个月增长动量为 {topic['momentum']}%。"
            ),
            "time": topic["updated_at"],
            "impact": topic["hotness"],
            "color": "red" if topic["trend_direction"] == "rising" else "blue",
            "topic_ids": [topic["id"]],
        }

    def _detect_phases(self, monthly_data: list[dict]) -> list[dict]:
        """Detect six-month development phases from monthly paper counts."""
        if len(monthly_data) < 6:
            return []

        counts = [item["count"] for item in monthly_data]
        months = [item["month"] for item in monthly_data]
        if sum(counts) == 0:
            return [{
                "phase": "emerging",
                "start_month": months[0],
                "end_month": months[-1],
                "description": "该主题暂无显著论文数据，处于萌芽阶段",
            }]

        phases = []
        window = 6
        overall_average = sum(counts) / len(counts)
        for index in range(0, len(counts) - window + 1, window):
            segment = counts[index : index + window]
            average = sum(segment) / window
            if sum(segment) == 0:
                continue
            first_half = sum(segment[:3])
            second_half = sum(segment[3:])
            if second_half > first_half * 1.2:
                phase, description = "growing", "论文数量持续增长，研究关注度上升"
            elif first_half > second_half * 1.3:
                phase, description = "declining", "论文数量下降，主题进入调整阶段"
            elif average >= overall_average:
                phase, description = "mature", "论文产出较稳定，研究进入成熟阶段"
            else:
                phase, description = "emerging", "论文开始出现，主题处于探索阶段"
            phases.append({
                "phase": phase,
                "start_month": months[index],
                "end_month": months[min(index + window - 1, len(months) - 1)],
                "description": description,
            })
        return phases or [{
            "phase": "emerging",
            "start_month": months[0],
            "end_month": months[-1],
            "description": "该主题处于发展初期",
        }]

    @staticmethod
    def _empty_overview() -> dict:
        return {
            "topics": [],
            "signals": [],
            "related_concepts_by_topic_id": {},
            "category_options": ["全部"],
        }


trend_service = TrendService()
