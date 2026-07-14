"""Map-reduce extraction and Markdown rendering for paper analysis."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from app.config import Settings, settings
from app.core.llm_gateway import LLMGateway
from app.schemas.analysis import (
    ChunkExtraction,
    ExtractedConcept,
    FinalExtraction,
)
from app.services.chunking import PaperTextChunk


class StructuredExtractionError(ValueError):
    """Raised when an LLM response is not valid JSON for the requested schema."""


@dataclass(slots=True)
class ExtractionResult:
    final: FinalExtraction
    local: list[ChunkExtraction]
    structured_content: dict[str, Any]


def parse_json_object(raw: str) -> dict[str, Any]:
    """Parse a JSON object, accepting a fenced JSON response but no prose."""

    candidate = raw.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", candidate, re.S | re.I)
    if fenced:
        candidate = fenced.group(1)
    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start >= 0 and end > start:
            candidate = candidate[start : end + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise StructuredExtractionError("LLM response is not valid JSON") from exc
    if not isinstance(value, dict):
        raise StructuredExtractionError("LLM response must be a JSON object")
    return value


def _json_schema_hint() -> str:
    return json.dumps(
        {
            "summary": "中文摘要",
            "research_question": "研究问题",
            "contributions": ["贡献"],
            "methods": ["方法"],
            "experiments": ["实验和结果"],
            "concepts": [
                {
                    "name_en": "standard English term",
                    "name_zh": "中文别名",
                    "description": "中文说明",
                    "category": "category",
                    "evidence": "原文证据",
                    "relevance": 0.9,
                }
            ],
            "relations": [
                {
                    "source": "standard English term",
                    "target": "another term",
                    "relation_type": "USES",
                    "evidence": "原文证据",
                    "confidence": 0.8,
                }
            ],
            "references": [
                {
                    "arxiv_id": "2301.00001",
                    "title": "paper title",
                    "authors": ["author"],
                    "context": "引用上下文",
                    "confidence": 0.8,
                }
            ],
        },
        ensure_ascii=False,
    )


def build_chunk_prompt(title: str, abstract: str, chunk: PaperTextChunk) -> str:
    return f"""你是科学论文知识抽取器。请只返回一个可被 JSON 解析的对象，不要 Markdown，不要解释。
输出字段必须参考这个结构：{_json_schema_hint()}
所有说明用中文；概念必须同时给出规范英文名和中文别名；证据必须来自给定文本，不要臆造。

论文标题：{title}
论文摘要：{abstract}
章节：{chunk.section_title or '正文'}
片段：
{chunk.content}
"""


def build_reduce_prompt(title: str, abstract: str, local_results: list[ChunkExtraction]) -> str:
    local_json = json.dumps(
        [result.model_dump(mode="json") for result in local_results], ensure_ascii=False
    )
    return f"""你是论文分析汇总器。请只返回一个可被 JSON 解析的对象，不要 Markdown，不要解释。
把局部抽取结果合并为一份去重后的中文分析，概念保留标准英文名，中文名放入 name_zh。
summary、research_question、concept_description 使用完整中文句子；methods、experiments、contributions 使用列表。
references 保留无法确认的引用，不要创建虚构的 arXiv ID。关系类型使用 IS_A、USES、IMPROVES、RELATED_TO 等大写值。
输出字段参考：{_json_schema_hint()}

论文标题：{title}
论文摘要：{abstract}
局部结果 JSON：
{local_json}
"""


def _nonempty(values: list[str]) -> list[str]:
    return [value.strip() for value in values if isinstance(value, str) and value.strip()]


def _concept_markdown(concepts: list[ExtractedConcept], description: str) -> str:
    lines = ["## 核心概念", ""]
    if description.strip():
        lines.extend([description.strip(), ""])
    rendered = 0
    for concept in concepts:
        if not concept.name_en.strip():
            continue
        alias = f"（{concept.name_zh.strip()}）" if concept.name_zh.strip() else ""
        detail = f"：{concept.description.strip()}" if concept.description.strip() else ""
        lines.append(f"- **{concept.name_en.strip()}**{alias}{detail}")
        rendered += 1
    if rendered == 0:
        lines.append("- 暂未识别到明确概念。")
    return "\n".join(lines)


def _methods_markdown(extraction: FinalExtraction) -> str:
    lines = ["## 方法", ""]
    methods = _nonempty(extraction.methods)
    lines.extend(f"{index}. {method}" for index, method in enumerate(methods, 1))
    if not methods:
        lines.append("1. 论文未提供可结构化的方法描述。")
    return "\n".join(lines)


def render_markdown(extraction: FinalExtraction, *, fallback_summary: str = "") -> dict[str, str]:
    summary = extraction.summary.strip() or fallback_summary.strip() or "论文摘要未提供。"
    summary_lines = ["## 论文摘要", "", summary]
    if extraction.research_question.strip():
        summary_lines.extend(["", "## 研究问题", "", extraction.research_question.strip()])
    if extraction.contributions:
        summary_lines.extend(["", "## 主要贡献", ""])
        summary_lines.extend(f"- {item}" for item in _nonempty(extraction.contributions))
    if extraction.experiments:
        summary_lines.extend(["", "## 实验与结果", ""])
        summary_lines.extend(f"- {item}" for item in _nonempty(extraction.experiments))
    return {
        "summary": "\n".join(summary_lines),
        "concept": _concept_markdown(extraction.concepts, extraction.concept_description),
        "methods": _methods_markdown(extraction),
    }


class StructuredExtractor:
    def __init__(self, llm: LLMGateway, config: Settings = settings):
        self.llm = llm
        self.config = config

    async def extract(self, *, title: str, abstract: str, chunks: list[PaperTextChunk]) -> ExtractionResult:
        if not chunks:
            raise StructuredExtractionError("No chunks are available for LLM extraction")
        local_results: list[ChunkExtraction] = []
        for chunk in chunks:
            raw = await self.llm.generate(
                build_chunk_prompt(title, abstract, chunk),
                system_prompt="Return JSON only. Validate every field against the requested structure.",
            )
            try:
                local_results.append(ChunkExtraction.model_validate(parse_json_object(raw)))
            except Exception as exc:
                if isinstance(exc, StructuredExtractionError):
                    raise
                raise StructuredExtractionError("Local extraction failed schema validation") from exc

        reduced_raw = await self.llm.generate(
            build_reduce_prompt(title, abstract, local_results),
            system_prompt="Return JSON only. Merge duplicate concepts and preserve evidence.",
        )
        try:
            final = FinalExtraction.model_validate(parse_json_object(reduced_raw))
        except Exception as exc:
            if isinstance(exc, StructuredExtractionError):
                raise
            raise StructuredExtractionError("Reduce extraction failed schema validation") from exc
        markdown = render_markdown(final, fallback_summary=abstract)
        structured = {
            **markdown,
            "researchQuestion": final.research_question,
            "experiments": _nonempty(final.experiments),
            "contributions": _nonempty(final.contributions),
            "references": [reference.model_dump(mode="json") for reference in final.references],
            "analysisVersion": self.config.analysis_version,
            "promptVersion": self.config.analysis_prompt_version,
            "model": self.config.llm_model,
        }
        return ExtractionResult(final=final, local=local_results, structured_content=structured)


__all__ = [
    "ExtractionResult",
    "StructuredExtractionError",
    "StructuredExtractor",
    "build_chunk_prompt",
    "build_reduce_prompt",
    "parse_json_object",
    "render_markdown",
]
