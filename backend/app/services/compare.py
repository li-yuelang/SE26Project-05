"""Business logic for paper comparison."""
from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.learning import PaperComparison
from app.models.paper import Paper, UserPaper
from app.models.user import User

logger = logging.getLogger(__name__)


class CompareService:
    """Stateless service for paper comparison operations."""

    async def create_comparison(
        self, db: AsyncSession, user: User, title: str, paper_ids: list[UUID],
    ) -> dict:
        papers = (
            await db.scalars(
                select(Paper).join(UserPaper).where(Paper.id.in_(paper_ids), UserPaper.user_id == user.id)
            )
        ).all()
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
        papers = (
            await db.scalars(
                select(Paper).join(UserPaper).where(Paper.id.in_(paper_uuids), UserPaper.user_id == user.id)
            )
        ).all()

        papers_data = []
        unanalysed_ids: list[UUID] = []
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
                "parsed_status": p.parsed_status or "pending",
            })
            if p.parsed_status not in ("completed", "processing"):
                unanalysed_ids.append(p.id)

        # Block comparison if any paper is not yet parsed
        if unanalysed_ids:
            unparsed_info = []
            for p in papers:
                if p.id in unanalysed_ids:
                    unparsed_info.append({
                        "paper_id": str(p.id),
                        "title": p.title,
                        "parsed_status": p.parsed_status or "pending",
                    })
            raise ValueError(json.dumps({"unparsed_papers": unparsed_info}))

        # If a report hasn't been generated yet and LLM is configured, generate one
        report_content = comparison.report_content
        matrix_data = None
        if not report_content:
            result = await self._generate_report(papers_data, comparison.title)
            if result:
                report_content = result.get("report", "")
                matrix_data = result.get("matrix")
                if report_content:
                    comparison.report_content = report_content
                    await db.commit()
        else:
            # Try to parse existing report_content as JSON to extract matrix
            try:
                parsed = json.loads(report_content)
                if isinstance(parsed, dict) and "matrix" in parsed:
                    report_content = parsed.get("report", report_content)
                    matrix_data = parsed.get("matrix")
            except (json.JSONDecodeError, TypeError):
                # Old format (plain markdown), keep as-is
                pass

        return {
            "comparison_id": str(comparison.id),
            "title": comparison.title,
            "papers": papers_data,
            "report_content": report_content,
            "matrix": matrix_data,
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
    async def _generate_report(papers_data: list[dict], title: str) -> dict | None:
        """Use LLM to generate a comparative analysis report with structured matrix."""
        if len(papers_data) < 2:
            return None

        try:
            from app.core import get_llm_gateway

            llm = get_llm_gateway()
        except Exception:
            logger.warning("Unable to initialise the LLM for comparison %r", title, exc_info=True)
            return None

        # Assign paper labels for the matrix
        paper_labels = {}
        for i, p in enumerate(papers_data, 1):
            paper_labels[p["paper_id"]] = f"论文{i}"

        # Build a structured prompt with paper information
        papers_text = ""
        for i, p in enumerate(papers_data, 1):
            papers_text += f"""
论文 {i}: {p['title']}
论文ID: {p['paper_id']}
作者: {', '.join(p['authors'][:5]) if p['authors'] else '未知'}
类别: {p['primary_category']}
摘要: {p['abstract'][:600]}
方法: {p.get('methods', '无')[:400]}
结论: {p.get('experiments', '无')[:400]}
"""

        dimensions = ["研究问题", "核心方法", "数据与实验", "主要结论", "局限性", "适合参考"]

        system_prompt = """你是一个学术论文分析专家。你的输出必须是严格的 JSON 格式，不要包含任何 markdown 标记或额外文字。"""
        prompt = f"""请对以下 {len(papers_data)} 篇论文进行对比分析，主题: {title}

{papers_text}

请从以下 6 个维度对每篇论文进行分析，并以严格的 JSON 格式返回:
{json.dumps(dimensions, ensure_ascii=False)}

返回格式:
{{
  "report": "markdown 格式的完整对比分析报告（包含各维度的对比分析）",
  "matrix": {{
    "研究问题": {{"<paper_id>": "该论文研究问题的描述", ...}},
    "核心方法": {{"<paper_id>": "该论文核心方法的描述", ...}},
    "数据与实验": {{"<paper_id>": "该论文数据与实验的描述", ...}},
    "主要结论": {{"<paper_id>": "该论文主要结论的描述", ...}},
    "局限性": {{"<paper_id>": "该论文局限性的描述", ...}},
    "适合参考": {{"<paper_id>": "该论文适合参考的描述", ...}}
  }}
}}

每个维度的值应该是对比视角下的分析（而非简单复制论文原文摘要），突出各论文在该维度上的差异和特点。
控制在 1200 字以内，使用中文。确保返回有效的 JSON。"""
        try:
            logger.info("Generating AI comparison report for %d papers", len(papers_data))
            raw = await llm.generate(prompt, system_prompt=system_prompt)
            if not raw:
                return None

            # Parse JSON from response (handle possible markdown fences)
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                # Remove markdown code fences
                lines = cleaned.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned = "\n".join(lines).strip()

            result = json.loads(cleaned)
            return result
        except (json.JSONDecodeError, TypeError):
            logger.warning("Failed to parse JSON from LLM response", exc_info=True)
            return None
        except Exception:
            logger.warning("AI comparison report generation failed", exc_info=True)
            return None


compare_service = CompareService()
