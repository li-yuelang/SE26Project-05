import json
import asyncio

import pytest

from app.config import Settings
from app.core.embedding import EmbeddingProviderError, OpenAICompatibleEmbeddingProvider
from app.schemas.analysis import FinalExtraction
from app.services.analysis_extractor import StructuredExtractor, parse_json_object, render_markdown
from app.services.analysis_persistence import (
    collect_concepts,
    normalize_arxiv_id,
    normalize_concept_name,
    normalize_title,
)
from app.services.chunking import SemanticChunker
from app.services.pdf_parser import (
    ParsedDocument,
    Section,
    TextBlock,
    identify_sections,
    is_back_matter_heading,
)
from app.services.paper_analysis import PDFDownloadError, download_pdf
from app.tasks.paper_tasks import _run_async


def test_heading_detection_and_margin_filtering() -> None:
    blocks = [
        TextBlock("Paper title", 1, (0, 20, 100, 40), 18, True),
        TextBlock("1 Introduction", 1, (0, 100, 100, 120), 14, True),
        TextBlock("The introduction explains the problem.", 1, (0, 140, 100, 170), 10),
        TextBlock("Paper title", 2, (0, 20, 100, 40), 18, True),
        TextBlock("2 Method", 2, (0, 100, 100, 120), 14, True),
        TextBlock("2.1 Encoder", 2, (0, 125, 100, 140), 12, True),
        TextBlock("The method is evaluated.", 2, (0, 140, 100, 170), 10),
        TextBlock("Paper title", 3, (0, 20, 100, 40), 18, True),
        TextBlock("3 Results", 3, (0, 100, 100, 120), 14, True),
        TextBlock("The results improve the baseline.", 3, (0, 140, 100, 170), 10),
    ]

    sections = identify_sections(blocks, page_count=3)

    assert [section.title for section in sections] == ["1 Introduction", "2 Method", "2.1 Encoder", "3 Results"]
    assert sections[2].level == 2
    assert "Paper title" not in " ".join(section.text for section in sections)


@pytest.mark.parametrize(
    "heading",
    [
        "References",
        "References:",
        "7. REFERENCES",
        "IX. References.",
        "Bibliography",
        "Works Cited",
        "Appendix A: Additional Results",
        "Supplementary Material",
        "参考文献",
        "附录A：证明",
    ],
)
def test_back_matter_heading_variants(heading: str) -> None:
    assert is_back_matter_heading(heading)


def test_section_detection_stops_before_references_and_appendices() -> None:
    blocks = [
        TextBlock("1 Introduction", 1, font_size=14, is_bold=True),
        TextBlock("The paper introduces a useful method.", 1, font_size=10),
        TextBlock("2 Results", 2, font_size=14, is_bold=True),
        TextBlock("The method improves the baseline.", 2, font_size=10),
        TextBlock("3 References", 3, font_size=14, is_bold=True),
        TextBlock("[1] A very long bibliography entry.", 3, font_size=10),
        TextBlock("Appendix A: Extra tables", 4, font_size=14, is_bold=True),
        TextBlock("Expensive back-matter content.", 4, font_size=10),
    ]

    sections = identify_sections(blocks, page_count=4)

    assert [section.title for section in sections] == ["1 Introduction", "2 Results"]
    assert "bibliography" not in " ".join(section.text for section in sections)
    assert "Expensive" not in " ".join(section.text for section in sections)


def test_document_containing_only_back_matter_produces_no_sections() -> None:
    sections = identify_sections(
        [
            TextBlock("References", 1, font_size=14, is_bold=True),
            TextBlock("[1] Citation only.", 1, font_size=10),
        ]
    )

    assert sections == []


def test_back_matter_matching_does_not_treat_a_sentence_as_the_cutoff() -> None:
    assert not is_back_matter_heading("References are discussed in the related-work section")
    assert not is_back_matter_heading("Appendix describes how sequences are concatenated")


def test_chunker_keeps_section_boundaries_and_indexes() -> None:
    sections = [
        Section(
            title="Introduction",
            blocks=[TextBlock("A " * 45, 1)],
        ),
        Section(
            title="Method",
            blocks=[TextBlock("B " * 45, 2)],
        ),
    ]
    document = ParsedDocument(sections=sections, blocks=[block for section in sections for block in section.blocks], parser_name="fake", page_count=2)

    chunks = SemanticChunker(target_tokens=20, max_tokens=25, overlap_tokens=0).chunk(document)

    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert {chunk.section_title for chunk in chunks} == {"Introduction", "Method"}
    assert all(chunk.token_count <= 25 for chunk in chunks)


def test_chunker_skips_back_matter_from_prebuilt_sections() -> None:
    sections = [
        Section("Introduction", blocks=[TextBlock("Useful body text.", 1)]),
        Section("References", blocks=[TextBlock("[1] Costly citation text.", 2)]),
        Section("Appendix A", blocks=[TextBlock("Costly appendix text.", 3)]),
    ]

    chunks = SemanticChunker(target_tokens=20, max_tokens=25, overlap_tokens=0).chunk(sections)

    assert [chunk.section_title for chunk in chunks] == ["Introduction"]
    assert chunks[0].content == "Useful body text."


def test_markdown_rendering_has_required_nonempty_fields() -> None:
    extraction = FinalExtraction(
        summary="这是一项研究。",
        research_question="如何提升检索？",
        methods=["构建向量索引"],
        concepts=[{"name_en": "Vector Search", "name_zh": "向量检索", "description": "语义检索"}],
    )

    markdown = render_markdown(extraction)

    assert set(markdown) == {"summary", "concept", "methods"}
    assert all(value.strip() for value in markdown.values())
    assert "Vector Search" in markdown["concept"]


def test_concept_merge_and_identifier_normalisation() -> None:
    final = FinalExtraction(
        concepts=[
            {"name_en": "Graph Neural Networks", "name_zh": "图神经网络"},
            {"name_en": "graph-neural networks", "name_zh": "GNN"},
        ],
        relations=[{"source": "图神经网络", "target": "RAG", "relation_type": "USES"}],
    )
    concepts, relations = collect_concepts(final)

    assert list(concepts).count("graph neural networks") == 1
    assert relations[0].source_key == "graph neural networks"
    assert "图神经网络" in concepts["graph neural networks"].aliases
    assert normalize_concept_name("Graph-Neural Networks") == "graph neural networks"
    assert normalize_arxiv_id("https://arxiv.org/abs/2301.00001v2") == "2301.00001"
    assert normalize_title("A Study: On Retrieval") == "a study on retrieval"


class FakeLLM:
    def __init__(self, responses: list[dict]):
        self.responses = iter(responses)

    async def generate(self, prompt: str, *, system_prompt: str | None = None) -> str:
        del prompt, system_prompt
        return json.dumps(next(self.responses), ensure_ascii=False)


class FakeResponse:
    def __init__(self, body: dict):
        self.body = body

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.body


class FakeEmbeddingClient:
    def __init__(self, dimensions: int):
        self.dimensions = dimensions

    async def post(self, url: str, *, headers: dict, json: dict) -> FakeResponse:
        del url, headers
        return FakeResponse(
            {"data": [{"index": index, "embedding": [0.1] * self.dimensions} for index, _ in enumerate(json["input"])]}
        )


class FakeDownloadClient:
    def __init__(self, content: bytes, content_type: str = "application/pdf"):
        self.response = type(
            "Response",
            (),
            {"status_code": 200, "headers": {"content-type": content_type}, "content": content},
        )()

    async def get(self, url: str):
        del url
        return self.response


@pytest.mark.asyncio
async def test_fake_map_reduce_and_embedding_dimension_guard() -> None:
    llm = FakeLLM(
        [
            {"summary": "局部摘要", "concepts": [{"name_en": "RAG", "name_zh": "检索增强生成"}]},
            {"summary": "完整摘要", "methods": ["检索"], "concepts": [{"name_en": "RAG", "name_zh": "检索增强生成"}]},
        ]
    )
    result = await StructuredExtractor(llm).extract(
        title="Test paper", abstract="Abstract", chunks=[
            type("Chunk", (), {"section_title": "Introduction", "content": "Text"})()
        ],
    )
    assert result.structured_content["summary"]
    assert result.structured_content["concept"]
    assert result.structured_content["methods"]
    assert parse_json_object("```json\n{\"ok\": true}\n```")["ok"] is True

    config = Settings(llm_api_key="test", embedding_dimension=1536)
    provider = OpenAICompatibleEmbeddingProvider(config, FakeEmbeddingClient(1535))
    with pytest.raises(EmbeddingProviderError, match="dimension"):
        await provider.embed(["text"])


@pytest.mark.asyncio
async def test_pdf_download_rejects_unavailable_or_non_pdf_content() -> None:
    with pytest.raises(PDFDownloadError, match="Content-Type"):
        await download_pdf("https://example.test/paper", client=FakeDownloadClient(b"<html>", "text/html"))
    with pytest.raises(PDFDownloadError, match="not a PDF"):
        await download_pdf("https://example.test/paper", client=FakeDownloadClient(b"not pdf"))
    with pytest.raises(PDFDownloadError, match="size limit"):
        await download_pdf(
            "https://example.test/paper",
            config=Settings(analysis_pdf_max_bytes=4),
            client=FakeDownloadClient(b"%PDF-1.7"),
        )


@pytest.mark.asyncio
async def test_celery_eager_runner_supports_an_existing_event_loop() -> None:
    assert _run_async(asyncio.sleep(0, result="ok")) == "ok"
