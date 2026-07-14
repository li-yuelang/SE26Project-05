"""Text-first PDF parsing with lightweight section detection.

The parser deliberately keeps layout metadata small and useful: text, page,
bounding box and the strongest font signal in a block.  That is enough to
recognise common academic headings while avoiding a dependency on a full OCR
or document-layout pipeline, which is outside the first release scope.
"""

from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Any

try:  # Optional imports make parser unit tests runnable without PDF extras.
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal environments
    fitz = None

try:
    import pdfplumber  # type: ignore
except ImportError:  # pragma: no cover - exercised only in minimal environments
    pdfplumber = None


_NUMBERED_HEADING = re.compile(r"^(?:\d+(?:\.\d+)*[.)]?|[IVX]+[.)])\s+\S+", re.I)
_KNOWN_HEADING = re.compile(
    r"^(abstract|introduction|background|related work|preliminaries|method(?:ology)?|"
    r"approach|model|experiments?|results?|discussion|conclusion|limitations?|"
    r"future work|acknowledg(?:e)?ments?|references|appendix)\b",
    re.I,
)
_TOKEN_PATTERN = re.compile(r"[\u3400-\u9fff]|[A-Za-z0-9_]+|[^\s]", re.UNICODE)


@dataclass(slots=True)
class TextBlock:
    text: str
    page_number: int
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    font_size: float = 0.0
    is_bold: bool = False
    line_count: int = 1


@dataclass(slots=True)
class Section:
    title: str
    level: int = 1
    blocks: list[TextBlock] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n\n".join(block.text for block in self.blocks if block.text.strip())


@dataclass(slots=True)
class ParsedDocument:
    sections: list[Section]
    blocks: list[TextBlock]
    parser_name: str
    page_count: int

    @property
    def text(self) -> str:
        return "\n\n".join(section.text for section in self.sections if section.text)

    @property
    def character_count(self) -> int:
        return len(self.text)


def clean_block_text(value: str) -> str:
    value = value.replace("\u00a0", " ").replace("\u00ad", "")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\s*\n\s*", "\n", value)
    return value.strip()


def _normalise_for_repeat(value: str) -> str:
    return re.sub(r"[^\w\u3400-\u9fff]+", "", value.casefold())


def _is_heading(block: TextBlock, typical_font_size: float) -> bool:
    text = block.text.strip()
    if not text or len(text) > 220 or block.line_count > 3:
        return False
    if text.endswith((".", "。", ":", "：", ";", "；")) and not _NUMBERED_HEADING.match(text):
        return False
    if _KNOWN_HEADING.match(text) or _NUMBERED_HEADING.match(text):
        return True
    if block.is_bold and len(text.split()) <= 14:
        return True
    return block.font_size >= typical_font_size * 1.18 and len(text.split()) <= 14


def _heading_level(text: str, block: TextBlock, typical_font_size: float) -> int:
    numeric = re.match(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+", text.strip())
    if numeric:
        return max(1, numeric.group(1).count(".") + 1)
    roman = re.match(r"^([IVX]+)(?:[.)])?\s+", text.strip(), re.I)
    if roman:
        return 1
    if block.font_size >= typical_font_size * 1.35:
        return 1
    return 2


def _remove_repeated_margins(blocks: list[TextBlock], page_count: int) -> list[TextBlock]:
    if page_count < 3:
        return blocks
    candidates: Counter[str] = Counter()
    for block in blocks:
        _, top, _, bottom = block.bbox
        if len(block.text) <= 160 and (top <= 90 or bottom >= 680):
            key = _normalise_for_repeat(block.text)
            if key:
                candidates[key] += 1
    repeated = {
        key for key, count in candidates.items() if count >= max(3, math.ceil(page_count * 0.6))
    }
    return [block for block in blocks if _normalise_for_repeat(block.text) not in repeated]


def identify_sections(blocks: list[TextBlock], page_count: int | None = None) -> list[Section]:
    """Group blocks into heading-delimited sections and remove page furniture."""

    if not blocks:
        return []
    page_count = page_count or max(block.page_number for block in blocks)
    blocks = _remove_repeated_margins(blocks, page_count)
    font_sizes = [block.font_size for block in blocks if block.font_size > 0]
    typical_font_size = median(font_sizes) if font_sizes else 10.0

    sections: list[Section] = []
    current = Section(title="前言", level=1)
    for block in blocks:
        if _is_heading(block, typical_font_size):
            if current.blocks or current.title != "前言":
                sections.append(current)
            current = Section(
                title=block.text.strip(),
                level=_heading_level(block.text, block, typical_font_size),
            )
        else:
            current.blocks.append(block)
    if current.blocks or current.title != "前言":
        sections.append(current)

    if not sections:
        return [Section(title="正文", level=1, blocks=blocks)]
    return sections


def _extract_with_pymupdf(pdf_bytes: bytes) -> tuple[list[TextBlock], int]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed")
    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    blocks: list[TextBlock] = []
    try:
        for page_index, page in enumerate(document):
            page_dict: dict[str, Any] = page.get_text("dict")
            for raw_block in page_dict.get("blocks", []):
                if raw_block.get("type") != 0:
                    continue
                spans = [
                    span
                    for line in raw_block.get("lines", [])
                    for span in line.get("spans", [])
                    if span.get("text", "").strip()
                ]
                text = clean_block_text(" ".join(span.get("text", "") for span in spans))
                if not text:
                    continue
                bbox = tuple(float(value) for value in raw_block.get("bbox", (0, 0, 0, 0)))
                blocks.append(
                    TextBlock(
                        text=text,
                        page_number=page_index + 1,
                        bbox=bbox,  # type: ignore[arg-type]
                        font_size=max((float(span.get("size", 0)) for span in spans), default=0.0),
                        is_bold=any("bold" in str(span.get("font", "")).casefold() for span in spans),
                        line_count=max(1, len(raw_block.get("lines", []))),
                    )
                )
        return blocks, len(document)
    finally:
        document.close()


def _extract_with_pdfplumber(pdf_bytes: bytes) -> tuple[list[TextBlock], int]:
    if pdfplumber is None:
        raise RuntimeError("pdfplumber is not installed")
    blocks: list[TextBlock] = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as document:
        for page_index, page in enumerate(document.pages):
            page_text = page.extract_text() or ""
            for line_index, line in enumerate(page_text.splitlines()):
                text = clean_block_text(line)
                if not text:
                    continue
                blocks.append(
                    TextBlock(
                        text=text,
                        page_number=page_index + 1,
                        bbox=(0.0, float(line_index * 12), 0.0, float(line_index * 12 + 10)),
                        font_size=10.0,
                    )
                )
        return blocks, len(document.pages)


class PDFParser:
    """Parse text-layer PDFs with PyMuPDF and a pdfplumber fallback."""

    def __init__(self, *, min_characters_per_page: int = 40):
        self.min_characters_per_page = min_characters_per_page

    def parse(self, pdf_bytes: bytes) -> ParsedDocument:
        if not pdf_bytes.startswith(b"%PDF"):
            raise ValueError("The downloaded file is not a PDF")

        primary_error: Exception | None = None
        try:
            blocks, page_count = _extract_with_pymupdf(pdf_bytes)
            text_length = sum(len(block.text) for block in blocks)
            if text_length >= max(1, page_count * self.min_characters_per_page):
                return ParsedDocument(
                    sections=identify_sections(blocks, page_count),
                    blocks=blocks,
                    parser_name="pymupdf",
                    page_count=page_count,
                )
        except Exception as exc:  # fall through to the independent parser
            primary_error = exc

        try:
            blocks, page_count = _extract_with_pdfplumber(pdf_bytes)
        except Exception as fallback_error:
            if primary_error:
                raise ValueError("Unable to extract text from the PDF") from fallback_error
            raise
        text_length = sum(len(block.text) for block in blocks)
        if text_length < max(40, page_count * max(10, self.min_characters_per_page // 4)):
            raise ValueError("PDF has insufficient text-layer content")
        return ParsedDocument(
            sections=identify_sections(blocks, page_count),
            blocks=blocks,
            parser_name="pdfplumber",
            page_count=page_count,
        )

    def parse_bytes(self, pdf_bytes: bytes) -> ParsedDocument:
        return self.parse(pdf_bytes)


def parse_pdf(pdf_bytes: bytes) -> ParsedDocument:
    return PDFParser().parse(pdf_bytes)
