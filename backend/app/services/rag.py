from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.core.embedding import get_embedding_provider
from app.core.llm_gateway import get_llm_gateway
from app.models.paper import Paper, PaperChunk, UserPaper

logger = logging.getLogger(__name__)

SYSTEM_PROMPTS = {
    "concept": (
        "你是严谨的论文概念讲解助手。先给出定义，再说明机制、局限和适用条件。"
        "只能依据给定论文片段作答；每个关键结论后标注 [编号]，不确定时明确说明证据不足。"
    ),
    "comparison": (
        "你是科研方法对比助手。按共同目标、核心差异、实验条件、优缺点和选择建议组织回答。"
        "不得把不同论文的结论混为一谈；每个关键结论后标注 [编号]。"
    ),
    "lineage": (
        "你是研究脉络梳理助手。按时间或依赖关系说明问题、代表方法、改进点和未决问题。"
        "只能使用给定证据，并在关键结论后标注 [编号]。"
    ),
}


@dataclass
class RetrievedChunk:
    chunk: PaperChunk
    paper: Paper
    score: float


def detect_scenario(question: str, requested: str = "auto") -> str:
    if requested != "auto":
        return requested
    lowered = question.lower()
    if any(word in lowered for word in ("对比", "比较", "区别", "versus", " vs ", "差异")):
        return "comparison"
    if any(word in lowered for word in ("脉络", "演进", "发展", "沿革", "时间线", "lineage")):
        return "lineage"
    return "concept"


def _terms(text: str) -> set[str]:
    latin = set(re.findall(r"[a-z0-9][a-z0-9_-]+", text.lower()))
    chinese = re.findall(r"[\u4e00-\u9fff]", text)
    return latin | set(chinese) | {"".join(chinese[index : index + 2]) for index in range(len(chinese) - 1)}


def lexical_score(question: str, content: str, title: str = "") -> float:
    query_terms = _terms(question)
    if not query_terms:
        return 0.0
    content_terms = _terms(f"{title} {content}")
    overlap = len(query_terms & content_terms) / len(query_terms)
    title_overlap = len(query_terms & _terms(title)) / len(query_terms)
    return overlap + title_overlap * 0.35


async def retrieve(
    db: AsyncSession,
    question: str,
    *,
    user_id: UUID,
    paper_ids: list[UUID] | None = None,
    candidate_limit: int = 24,
    result_limit: int = 6,
) -> list[RetrievedChunk]:
    statement = (
        select(PaperChunk)
        .options(selectinload(PaperChunk.paper))
        .join(PaperChunk.paper)
        .join(UserPaper, UserPaper.paper_id == Paper.id)
        .where(
            UserPaper.user_id == user_id,
            PaperChunk.content.is_not(None),
            or_(
                Paper.active_analysis_run_id.is_(None),
                PaperChunk.analysis_run_id == Paper.active_analysis_run_id,
            ),
        )
    )
    if paper_ids is not None:
        statement = statement.where(PaperChunk.paper_id.in_(paper_ids))

    vector_distances: dict[UUID, float] = {}
    if settings.embedding_api_key or settings.llm_api_key:
        try:
            embedding = (await get_embedding_provider().embed([question]))[0]
            distance = PaperChunk.embedding.cosine_distance(embedding)
            vector_statement = (
                statement.where(PaperChunk.embedding.is_not(None)).order_by(distance).limit(candidate_limit)
            )
            vector_chunks = list((await db.scalars(vector_statement)).unique().all())
            vector_distances = {
                chunk.id: index / max(1, len(vector_chunks))
                for index, chunk in enumerate(vector_chunks)
            }
        except Exception:
            logger.warning("Vector retrieval unavailable; falling back to keyword retrieval", exc_info=True)
            vector_chunks = []
    else:
        vector_chunks = []

    keywords = sorted(term for term in _terms(question) if len(term) >= 2)[:8]
    keyword_statement = statement
    if keywords:
        keyword_statement = keyword_statement.where(
            or_(
                *[PaperChunk.content.ilike(f"%{term}%") for term in keywords],
                *[Paper.title.ilike(f"%{term}%") for term in keywords],
            )
        )
    keyword_chunks = list((await db.scalars(keyword_statement.limit(candidate_limit))).unique().all())

    candidates = {chunk.id: chunk for chunk in [*vector_chunks, *keyword_chunks]}
    if not candidates and paper_ids:
        candidates = {
            chunk.id: chunk
            for chunk in (await db.scalars(statement.limit(candidate_limit))).unique().all()
        }

    ranked = []
    for chunk in candidates.values():
        lexical = lexical_score(question, chunk.content, chunk.paper.title)
        vector = 1 - vector_distances.get(chunk.id, 1.0)
        score = lexical * 0.65 + vector * 0.35 if chunk.id in vector_distances else lexical
        ranked.append(RetrievedChunk(chunk=chunk, paper=chunk.paper, score=score))
    return sorted(ranked, key=lambda item: item.score, reverse=True)[:result_limit]


def build_prompt(question: str, chunks: list[RetrievedChunk], scenario: str) -> tuple[str, str]:
    evidence = "\n\n".join(
        (
            f"[{index}] 论文：{item.paper.title}（arXiv:{item.paper.arxiv_id}）\n"
            f"章节：{item.chunk.section_title or '未标注'}；片段：{item.chunk.chunk_index}\n"
            f"{item.chunk.content}"
        )
        for index, item in enumerate(chunks, start=1)
    )
    prompt = (
        f"问题：{question}\n\n可用论文证据：\n{evidence or '没有检索到可用证据。'}\n\n"
        "请直接回答问题。末尾增加“证据边界”一节，简述哪些内容无法由片段确认。"
    )
    return SYSTEM_PROMPTS[scenario], prompt


def fallback_answer(question: str, chunks: list[RetrievedChunk], scenario: str) -> str:
    if not chunks:
        return "当前论文库中没有检索到足以回答该问题的原文片段。请先导入并解析相关论文，或缩小问题范围。"
    labels = {"concept": "概念解释", "comparison": "方法对比", "lineage": "研究脉络"}
    lines = [f"基于论文库中的相关片段，以下是对“{question}”的{labels[scenario]}："]
    for index, item in enumerate(chunks[:4], start=1):
        excerpt = re.sub(r"\s+", " ", item.chunk.content).strip()
        if len(excerpt) > 260:
            excerpt = f"{excerpt[:260]}…"
        lines.append(f"\n{index}. {excerpt} [{index}]")
    lines.append("\n证据边界：当前回答仅归纳已入库片段；未在片段中出现的信息不作推断。")
    return "".join(lines)


async def answer(
    db: AsyncSession,
    question: str,
    *,
    user_id: UUID,
    paper_ids: list[UUID] | None = None,
    requested_scenario: str = "auto",
) -> tuple[str, list[RetrievedChunk], str]:
    scenario = detect_scenario(question, requested_scenario)
    chunks = await retrieve(db, question, user_id=user_id, paper_ids=paper_ids)
    if settings.llm_api_key and chunks:
        system_prompt, prompt = build_prompt(question, chunks, scenario)
        try:
            content = await get_llm_gateway().generate(prompt, system_prompt=system_prompt)
        except Exception:
            logger.warning("LLM generation unavailable; using grounded extractive answer", exc_info=True)
            content = fallback_answer(question, chunks, scenario)
    else:
        content = fallback_answer(question, chunks, scenario)
    return content, chunks, scenario
