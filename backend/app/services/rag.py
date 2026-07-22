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
        "请用中文详细回答。只能依据给定论文片段作答；每个关键结论后标注 [编号]，"
        "不确定时明确说明证据不足。"
    ),
    "comparison": (
        "你是科研方法对比助手。按共同目标、核心差异、实验条件、优缺点和选择建议组织回答。"
        "请用中文详细回答。不得把不同论文的结论混为一谈；每个关键结论后标注 [编号]。"
    ),
    "lineage": (
        "你是研究脉络梳理助手。按时间或依赖关系说明问题、代表方法、改进点和未决问题。"
        "请用中文详细回答。只能使用给定证据，并在关键结论后标注 [编号]。"
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

    # Metadata fallback: for papers without analysis chunks, use abstract as context
    if paper_ids and (not candidates or len(candidates) < result_limit):
        hit_paper_ids = {c.paper_id for c in candidates.values() if hasattr(c, 'paper_id')}
        missing_ids = [pid for pid in paper_ids if pid not in hit_paper_ids]
        if missing_ids:
            fallback_papers = (await db.scalars(select(Paper).where(Paper.id.in_(missing_ids)))).all()
            for paper in fallback_papers:
                if not paper.abstract:
                    continue
                synthetic = PaperChunk(
                    paper_id=paper.id,
                    chunk_index=-1,
                    section_title="论文摘要",
                    content=paper.abstract[:1500],
                    analysis_run_id=None,
                )
                synthetic.paper = paper
                import uuid as _uuid
                synthetic.id = _uuid.uuid4()
                score = lexical_score(question, synthetic.content, paper.title) * 0.3
                candidates[id(synthetic)] = RetrievedChunk(
                    chunk=synthetic, paper=paper, score=score
                )

    ranked = []
    for candidate in candidates.values():
        if isinstance(candidate, RetrievedChunk):
            ranked.append(candidate)
            continue
        lexical = lexical_score(question, candidate.content, candidate.paper.title)
        vector = 1 - vector_distances.get(candidate.id, 1.0)
        score = lexical * 0.65 + vector * 0.35 if candidate.id in vector_distances else lexical
        ranked.append(RetrievedChunk(chunk=candidate, paper=candidate.paper, score=score))
    return sorted(ranked, key=lambda item: item.score, reverse=True)[:result_limit]


GENERAL_SYSTEM_PROMPT = (
    "你是 arxiv-PaperMate 智能助手，帮助研究者理解学术论文。"
    "当用户的问题与论文内容相关且有检索到的论文证据时，请用中文详细回答，"
    "基于证据充分展开，并在关键结论后标注 [编号]，末尾增加“证据边界”一节。\n"
    "当问题与论文无关（如日常对话、问候等），请自然友好地回答，无需强行关联论文。"
)


def is_general_chat(question: str) -> bool:
    """检测是否属于日常对话而非论文相关问题。"""
    lowered = question.strip().lower()
    general_patterns = {
        "你好", "hello", "hi", "hey", "早上好", "下午好", "晚上好",
        "你是谁", "你能做什么", "help", "感谢", "谢谢", "thanks",
    }
    if lowered in general_patterns or lowered.rstrip("！!。.？?") in general_patterns:
        return True
    return False


def build_prompt(question: str, chunks: list[RetrievedChunk], scenario: str) -> tuple[str, str]:
    evidence_parts = []
    for index, item in enumerate(chunks, start=1):
        if item.chunk.chunk_index == -1:
            portion = "摘要"
        else:
            portion = f"章节：{item.chunk.section_title or '未标注'}；片段：{item.chunk.chunk_index}"
        evidence_parts.append(
            f"[{index}] 论文：{item.paper.title}（arXiv:{item.paper.arxiv_id}）\n"
            f"{portion}\n{item.chunk.content}"
        )
    evidence = "\n\n".join(evidence_parts)
    prompt = (
        f"问题：{question}\n\n可用论文证据：\n{evidence or '没有检索到可用证据。'}\n\n"
        "请用中文详细回答，基于论文证据充分展开论述。"
        "末尾增加“证据边界”一节，简述哪些内容无法由片段确认。"
    )
    return SYSTEM_PROMPTS[scenario], prompt


def fallback_answer(question: str, chunks: list[RetrievedChunk], scenario: str) -> str:
    if not chunks:
        return (
            "当前论文库中没有检索到与你的问题直接相关的原文片段。"
            "请问你能提供更多背景信息，或者换个问题试试吗？"
        )


async def answer(
    db: AsyncSession,
    question: str,
    *,
    user_id: UUID,
    paper_ids: list[UUID] | None = None,
    requested_scenario: str = "auto",
) -> tuple[str, list[RetrievedChunk], str]:
    # 日常对话直接调 LLM 回答，不检索论文
    if is_general_chat(question):
        if settings.llm_api_key:
            try:
                content = await get_llm_gateway().generate(
                    question,
                    system_prompt="你是 arxiv-PaperMate 智能助手，友善、简洁地用中文回答用户的问题。",
                )
                return content, [], "general"
            except Exception:
                logger.warning("LLM unavailable for general chat", exc_info=True)
        return _general_fallback(question), [], "general"

    scenario = detect_scenario(question, requested_scenario)
    chunks = await retrieve(db, question, user_id=user_id, paper_ids=paper_ids)

    if not chunks and settings.llm_api_key:
        # 没检索到论文证据，但让 LLM 用自己的知识回答
        try:
            content = await get_llm_gateway().generate(
                f"用户的问题是：{question}\n\n"
                "当前论文库中没有检索到相关论文证据。请基于你自己的知识用中文回答这个问题。"
                "如果问题与学术论文相关但你不确定，请如实说明。",
                system_prompt="你是 arxiv-PaperMate 智能助手，帮助研究者理解学术论文。用中文清晰回答。",
            )
            return content, [], scenario
        except Exception:
            logger.warning("LLM unavailable; using fallback answer", exc_info=True)

    if settings.llm_api_key and chunks:
        system_prompt, prompt = build_prompt(question, chunks, scenario)
        try:
            content = await get_llm_gateway().generate(prompt, system_prompt=system_prompt)
            return content, chunks, scenario
        except Exception as exc:
            logger.warning("LLM generation failed: %s; using fallback", exc, exc_info=True)

    content = fallback_answer(question, chunks, scenario)
    return content, chunks, scenario


def _general_fallback(question: str) -> str:
    return (
        "你好！我是 PaperMate 智能助手，帮你查询和理解学术论文。"
        "你可以问我论文相关的问题，比如“Transformer 是什么？”或“对比 BERT 和 GPT”。"
    )
