"""Map-reduce extraction and Markdown rendering for paper analysis."""

from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from app.config import Settings, settings
from app.core.llm_gateway import LLMGateway
from app.schemas.analysis import (
    ChunkExtraction,
    ExtractedConcept,
    FinalExtraction,
)
from app.services.chunking import PaperTextChunk

logger = logging.getLogger(__name__)


class StructuredExtractionError(ValueError):
    """Raised when an LLM response is not valid JSON for the requested schema."""

    error_code = "EXTRACTION_ERROR"
    retryable = True


@dataclass(slots=True)
class ExtractionResult:
    final: FinalExtraction
    local: list[ChunkExtraction]
    structured_content: dict[str, Any]


def _repair_truncated_json(text: str) -> str | None:
    """Best-effort repair of truncated JSON: close unterminated strings and balance braces."""

    repaired = text
    in_string = False
    escape = False
    brace_depth = 0
    bracket_depth = 0

    for ch in repaired:
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
        elif ch == "[":
            bracket_depth += 1
        elif ch == "]":
            bracket_depth -= 1

    if in_string:
        repaired += '"'

    repaired += "]" * max(0, bracket_depth)
    repaired += "}" * max(0, brace_depth)

    try:
        json.loads(repaired)
        return repaired
    except json.JSONDecodeError:
        return None


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
        repaired = _repair_truncated_json(candidate)
        if repaired is not None:
            try:
                value = json.loads(repaired)
            except json.JSONDecodeError:
                raise StructuredExtractionError("LLM response is not valid JSON") from exc
        else:
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
    return f"""你是科学论文知识抽取器。请只返回 JSON data，用 ```json 和 ``` 包裹，不要解释。
输出字段必须参考这个结构：
```json
{_json_schema_hint()}
```
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
    return f"""你是论文分析汇总器。请只返回 JSON data，用 ```json 和 ``` 包裹，不要解释。
把局部抽取结果合并为一份去重后的中文分析，概念保留标准英文名，中文名放入 name_zh。
summary、research_question、concept_description 使用完整中文句子；methods、experiments、contributions 使用列表。
references 保留无法确认的引用，不要创建虚构的 arXiv ID。关系类型使用 IS_A、USES、IMPROVES、RELATED_TO 等大写值。
输出字段参考：
```json
{_json_schema_hint()}
```

论文标题：{title}
论文摘要：{abstract}
局部结果 JSON：
```json
{local_json}
```"""


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

    async def _extract_chunk(
        self, title: str, abstract: str, chunk: PaperTextChunk
    ) -> ChunkExtraction | None:
        """Extract one chunk, returning None if LLM fails after retries."""
        prompt = build_chunk_prompt(title, abstract, chunk)
        try:
            raw = await self.llm.generate(
                prompt,
                system_prompt="Return JSON inside ```json fence only. No explanation.",
            )
            return ChunkExtraction.model_validate(parse_json_object(raw))
        except Exception:
            pass

        # Retry once with conciseness hint + double max_tokens
        retry_prompt = (
            prompt
            + "\n\n注意：JSON 必须用 ```json 和 ``` 包裹，只返回最核心的信息，确保完整闭合。"
        )
        try:
            raw = await self.llm.generate(
                retry_prompt,
                system_prompt="Return JSON inside ```json fence. Keep concise. Validate schema.",
                max_tokens=self.config.llm_max_tokens * 2,
            )
            return ChunkExtraction.model_validate(parse_json_object(raw))
        except Exception:
            return None

    async def extract(
        self,
        *,
        title: str,
        abstract: str,
        chunks: list[PaperTextChunk],
        progress_callback: Callable[[], Awaitable[None]] | None = None,
    ) -> ExtractionResult:
        if not chunks:
            raise StructuredExtractionError("No chunks are available for LLM extraction")

        semaphore = asyncio.Semaphore(self.config.analysis_llm_max_concurrency)

        async def _extract_one(chunk: PaperTextChunk) -> tuple[int, ChunkExtraction | None]:
            """Extract a single chunk; returns (index, result_or_None)."""
            async with semaphore:
                if progress_callback is not None:
                    await progress_callback()
                result = await self._extract_chunk(title, abstract, chunk)
                if progress_callback is not None:
                    await progress_callback()
                return chunks.index(chunk), result

        # First pass: extract all chunks
        tasks = [_extract_one(chunk) for chunk in chunks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Collect success / failure indices
        local_results: dict[int, ChunkExtraction] = {}
        failed_indices: list[int] = []
        for item in results:
            if isinstance(item, tuple):
                idx, val = item
                if val is not None:
                    local_results[idx] = val
                else:
                    failed_indices.append(idx)
            else:
                # Unexpected exception in gather itself
                if isinstance(item, BaseException):
                    logger.warning("Extract task crashed: %s", item)

        # Retry failed chunks individually with trimmed prompt + triple max_tokens
        if failed_indices:
            retry_prompt_suffix = (
                "\n\n重要：只返回最核心的摘要和概念，JSON 必须用 ```json 和 ``` 包裹。"
            )
            async def _retry_one(idx: int) -> tuple[int, ChunkExtraction | None]:
                chunk = chunks[idx]
                prompt = build_chunk_prompt(title, abstract, chunk) + retry_prompt_suffix
                async with semaphore:
                    try:
                        raw = await self.llm.generate(
                            prompt,
                            system_prompt="Return a minimal valid JSON inside ```json fence.",
                            max_tokens=self.config.llm_max_tokens * 3,
                        )
                        return idx, ChunkExtraction.model_validate(parse_json_object(raw))
                    except Exception:
                        return idx, None

            retry_tasks = [_retry_one(idx) for idx in failed_indices]
            retry_results = await asyncio.gather(*retry_tasks, return_exceptions=True)
            for item in retry_results:
                if isinstance(item, tuple):
                    idx, val = item
                    if val is not None:
                        local_results[idx] = val

        # Final check: must have at least one successful extraction
        if not local_results:
            raise StructuredExtractionError(
                f"All {len(chunks)} chunk extractions failed after retries"
            )

        ordered = [local_results[i] for i in sorted(local_results)]

        reduced_raw = await self.llm.generate(
            build_reduce_prompt(title, abstract, ordered),
            system_prompt="Return JSON inside ```json fence. Merge duplicates, preserve evidence.",
        )
        try:
            final = FinalExtraction.model_validate(parse_json_object(reduced_raw))
        except Exception as exc:
            if isinstance(exc, StructuredExtractionError):
                raise
            raise StructuredExtractionError("Reduce extraction failed schema validation") from exc
        if progress_callback is not None:
            await progress_callback()
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
        return ExtractionResult(final=final, local=ordered, structured_content=structured)


__all__ = [
    "ExtractionResult",
    "StructuredExtractionError",
    "StructuredExtractor",
    "build_chunk_prompt",
    "build_reduce_prompt",
    "parse_json_object",
    "render_markdown",
]
