"""Section-aware semantic chunking for paper text."""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.pdf_parser import (
    ParsedDocument,
    Section,
    _TOKEN_PATTERN,
    is_back_matter_heading,
)


@dataclass(slots=True)
class PaperTextChunk:
    chunk_index: int
    section_title: str | None
    content: str
    token_count: int


def token_count(text: str) -> int:
    return len(_TOKEN_PATTERN.findall(text))


def _token_spans(text: str) -> list[tuple[int, int]]:
    return [(match.start(), match.end()) for match in _TOKEN_PATTERN.finditer(text)]


def _split_long_text(text: str, max_tokens: int) -> list[str]:
    spans = _token_spans(text)
    if len(spans) <= max_tokens:
        return [text.strip()]
    pieces: list[str] = []
    for offset in range(0, len(spans), max_tokens):
        start = spans[offset][0]
        end = spans[min(offset + max_tokens, len(spans)) - 1][1]
        pieces.append(text[start:end].strip())
    return [piece for piece in pieces if piece]


def _paragraphs(section: Section) -> list[str]:
    paragraphs: list[str] = []
    for block in section.blocks:
        for paragraph in re.split(r"\n\s*\n+|(?<=[。！？!?])\s+(?=[A-Z0-9\u3400-\u9fff])", block.text):
            paragraph = re.sub(r"\s+", " ", paragraph).strip()
            if paragraph:
                paragraphs.append(paragraph)
    return paragraphs


class SemanticChunker:
    def __init__(
        self,
        *,
        target_tokens: int = 500,
        max_tokens: int = 600,
        overlap_tokens: int = 50,
    ):
        if target_tokens <= 0 or max_tokens < target_tokens:
            raise ValueError("max_tokens must be greater than or equal to target_tokens")
        self.target_tokens = target_tokens
        self.max_tokens = max_tokens
        self.overlap_tokens = max(0, min(overlap_tokens, target_tokens // 2))

    def chunk(self, document: ParsedDocument | list[Section]) -> list[PaperTextChunk]:
        sections = document.sections if isinstance(document, ParsedDocument) else document
        chunks: list[PaperTextChunk] = []
        for section in sections:
            # Keep the cost-saving boundary even for callers that provide
            # pre-built sections rather than using PDFParser.
            if is_back_matter_heading(section.title):
                break
            paragraphs = _paragraphs(section)
            expanded: list[str] = []
            for paragraph in paragraphs:
                expanded.extend(_split_long_text(paragraph, self.max_tokens))

            current: list[str] = []
            current_tokens = 0
            for paragraph in expanded:
                paragraph_tokens = token_count(paragraph)
                would_exceed = current and current_tokens + paragraph_tokens > self.max_tokens
                should_close_at_target = current and current_tokens >= self.target_tokens
                if would_exceed or should_close_at_target:
                    chunks.append(self._make_chunk(len(chunks), section.title, current))
                    overlap = self._overlap(current)
                    current = overlap + [paragraph]
                    current_tokens = token_count(" ".join(current))
                else:
                    current.append(paragraph)
                    current_tokens += paragraph_tokens
            if current:
                chunks.append(self._make_chunk(len(chunks), section.title, current))
        return chunks

    def _overlap(self, paragraphs: list[str]) -> list[str]:
        if self.overlap_tokens <= 0:
            return []
        result: list[str] = []
        total = 0
        for paragraph in reversed(paragraphs):
            count = token_count(paragraph)
            if total + count > self.overlap_tokens:
                break
            result.insert(0, paragraph)
            total += count
        return result

    @staticmethod
    def _make_chunk(index: int, section_title: str | None, paragraphs: list[str]) -> PaperTextChunk:
        content = "\n\n".join(paragraph for paragraph in paragraphs if paragraph).strip()
        content = content.replace("\x00", "")
        safe_title = section_title.replace("\x00", "") if section_title else section_title
        return PaperTextChunk(
            chunk_index=index,
            section_title=safe_title,
            content=content,
            token_count=token_count(content),
        )


def chunk_document(
    document: ParsedDocument | list[Section],
    *,
    target_tokens: int = 500,
    max_tokens: int = 600,
    overlap_tokens: int = 50,
) -> list[PaperTextChunk]:
    return SemanticChunker(
        target_tokens=target_tokens,
        max_tokens=max_tokens,
        overlap_tokens=overlap_tokens,
    ).chunk(document)


semantic_chunk = chunk_document
