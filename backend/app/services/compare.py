"""Business logic for paper comparison."""
from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import PaperComparison
from app.models.paper import Paper
from app.models.user import User

logger = logging.getLogger(__name__)


class CompareService:
    """Stateless service for paper comparison operations."""

    async def create_comparison(
        self, db: AsyncSession, user: User, title: str, paper_ids: list[UUID],
    ) -> dict:
        papers = (await db.scalars(select(Paper).where(Paper.id.in_(paper_ids)))).all()
        if len(papers) < 2:
            raise ValueError("At least 2 valid papers are required for comparison")

        comparison = PaperComparison(
            user_id=user.id,
            title=title,
            paper_ids=[str(pid) for pid in paper_ids],
        )
        db.add(comparison)
        await db.commit()
        await db.refresh(comparison)
        return self._serialise(comparison)

    async def get_comparison(self, db: AsyncSession, user: User, comparison_id: UUID) -> dict:
        comparison = await db.scalar(
            select(PaperComparison)
            .where(PaperComparison.id == comparison_id, PaperComparison.user_id == user.id)
        )
        if comparison is None:
            raise ValueError("Comparison not found")
        return self._serialise(comparison)

    async def list_comparisons(
        self, db: AsyncSession, user: User, page: int = 1, page_size: int = 20,
    ) -> tuple[list[dict], int]:
        stmt = (
            select(PaperComparison)
            .where(PaperComparison.user_id == user.id)
            .order_by(PaperComparison.created_at.desc())
        )
        total = await db.scalar(select(func.count()).select_from(stmt.subquery()))
        offset = (page - 1) * page_size
        rows = (await db.scalars(stmt.offset(offset).limit(page_size))).all()
        return [self._serialise(r) for r in rows], total or 0

    async def delete_comparison(self, db: AsyncSession, user: User, comparison_id: UUID) -> None:
        result = await db.execute(
            select(PaperComparison).where(
                PaperComparison.id == comparison_id, PaperComparison.user_id == user.id
            )
        )
        comparison = result.scalar_one_or_none()
        if comparison is None:
            raise ValueError("Comparison not found")
        await db.delete(comparison)
        await db.commit()

    async def export_comparison(self, db: AsyncSession, user: User, comparison_id: UUID) -> dict:
        """Generate a rich comparison matrix, optionally with LLM analysis."""
        comparison = await db.scalar(
            select(PaperComparison)
            .where(PaperComparison.id == comparison_id, PaperComparison.user_id == user.id)
        )
        if comparison is None:
            raise ValueError("Comparison not found")

        paper_uuids = [UUID(pid) for pid in comparison.paper_ids]
        papers = (await db.scalars(select(Paper).where(Paper.id.in_(paper_uuids)))).all()

        papers_data = []
        for p in papers:
            structured = p.structured_content or {}
            papers_data.append({
                "paper_id": str(p.id),
                "arxiv_id": p.arxiv_id,
                "title": p.title,
                "authors": p.authors,
                "abstract": p.abstract,
                "primary_category": p.primary_category,
                "published_at": p.published_at.isoformat() if p.published_at else None,
                "summary": structured.get("summary", ""),
                "methods": structured.get("methods", ""),
                "concepts": structured.get("concepts", ""),
                "experiments": structured.get("experiments", ""),
            })

        # If a report hasn't been generated yet and LLM is configured, generate one
        report_content = comparison.report_content
        if not report_content:
            report_content = await self._generate_report(papers_data, comparison.title)
            if report_content:
                comparison.report_content = report_content
                await db.commit()

        return {
            "comparison_id": str(comparison.id),
            "title": comparison.title,
            "papers": papers_data,
            "report_content": report_content,
            "created_at": comparison.created_at.isoformat(),
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _serialise(comparison: PaperComparison) -> dict:
        return {
            "id": str(comparison.id),
            "title": comparison.title,
            "paper_ids": comparison.paper_ids or [],
            "report_content": comparison.report_content,
            "created_at": comparison.created_at,
            "updated_at": comparison.updated_at,
        }

    @staticmethod
    async def _generate_report(papers_data: list[dict], title: str) -> str | None:
        """Use LLM to generate a comparative analysis report."""
        if len(papers_data) < 2:
            return None

        try:
            from app.core import get_llm_gateway

            llm = get_llm_gateway()
        except Exception:
            logger.warning("Unable to initialise the LLM for comparison %r", title, exc_info=True)
            return None

        # Build a structured prompt with paper information
        papers_text = ""
        for i, p in enumerate(papers_data, 1):
            papers_text += f"""
论文 {i}: {p['title']}
作者: {', '.join(p['authors'][:5]) if p['authors'] else '未知'}
类别: {p['primary_category']}
摘要: {p['abstract'][:600]}
方法: {p.get('methods', '无')[:400]}
结论: {p.get('experiments', '无')[:400]}
"""

        system_prompt = "你是一个学术论文分析专家，请用中文撰写分析报告。"
        prompt = f"""请对以下 {len(papers_data)} 篇论文进行对比分析，主题: {title}

{papers_text}

请从以下几个维度撰写一份结构化的对比报告（使用 Markdown 格式）:
1. **研究问题对比** — 各论文解决的核心问题有何异同
2. **方法对比** — 采用的技术路线和方法论对比矩阵
3. **实验与结论** — 各论文的实验设置和主要结论
4. **优劣分析** — 各论文的优势与局限
5. **研究趋势** — 从这些论文看出的研究发展方向

请控制在 1200 字以内，使用中文。
"""
        try:
            logger.info("Generating AI comparison report for %d papers", len(papers_data))
            report = await llm.generate(prompt, system_prompt=system_prompt)
            return report if report else None
        except Exception:
            logger.warning("AI comparison report generation failed", exc_info=True)
            return None


compare_service = CompareService()
