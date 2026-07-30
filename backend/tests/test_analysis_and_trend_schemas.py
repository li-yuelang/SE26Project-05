"""Unit tests for LLM analysis normalization and trend response contracts."""

from types import SimpleNamespace
from uuid import uuid4

from app.schemas.analysis import (
    ChunkExtraction,
    ExtractedConcept,
    ExtractedReference,
    ExtractedRelation,
    FinalExtraction,
)
from app.schemas.trends import (
    TrendDetailOut,
    TrendMilestone,
    TrendMonthlyPoint,
    TrendOverview,
    TrendPhase,
    TrendSignalOut,
    TrendTopicSummary,
)


def test_analysis_contracts_normalize_aliases_and_mixed_text_values() -> None:
    concept = ExtractedConcept(
        english_name=[" Retrieval ", None, "Augmented"],
        chinese_name={"zh": "检索\x00增强"},
        description=42,
        category=" method ",
        evidence=[" first ", "", "second"],
        ignored_by_contract="value",
    )
    relation = ExtractedRelation(
        subject=" Retrieval ",
        object={"name": "Generation"},
        type=[" USES "],
        evidence=None,
    )

    assert concept.name_en == "Retrieval；Augmented"
    assert concept.name_zh == "zh: 检索增强"
    assert concept.description == "42"
    assert concept.category == "method"
    assert concept.evidence == "first；second"
    assert relation.source == "Retrieval"
    assert relation.target == "name: Generation"
    assert relation.relation_type == "USES"
    assert relation.evidence == ""
    assert "ignored_by_contract" not in concept.model_dump()


def test_reference_and_chunk_contracts_accept_provider_output_variants() -> None:
    empty_authors = ExtractedReference(arxivId=" 2401.00001 ", authors=None)
    one_author = ExtractedReference(id="paper", authors=" Ada ")
    many_authors = ExtractedReference(
        arxiv="paper-2",
        title=["A", "Title"],
        context={"section": " intro "},
        authors=[" Ada ", None, "", 7],
    )
    chunk = ChunkExtraction(
        summary={"result": " useful "},
        key_points=None,
        methods=" retrieval ",
    )

    assert empty_authors.authors == []
    assert one_author.authors == ["Ada"]
    assert many_authors.title == "A；Title"
    assert many_authors.context == "section: intro"
    assert many_authors.authors == ["Ada", "7"]
    assert chunk.summary == "result: useful"
    assert chunk.key_points == []
    assert chunk.methods == ["retrieval"]


def test_final_extraction_normalizes_scalar_and_list_fields() -> None:
    extraction = FinalExtraction(
        research_question=[" question one ", "question two"],
        concept_description=None,
        experiments=None,
        contributions=" main contribution ",
    )

    assert extraction.research_question == "question one；question two"
    assert extraction.concept_description == ""
    assert extraction.experiments == []
    assert extraction.contributions == ["main contribution"]


def test_trend_contracts_build_nested_overview_and_detail() -> None:
    topic_id = uuid4()
    source_topic = SimpleNamespace(
        id=topic_id,
        name="Retrieval-Augmented Generation",
        description=None,
        keywords=["RAG"],
        paper_count=12,
        hotness=88,
        trend_direction="rising",
    )
    topic = TrendTopicSummary.model_validate(source_topic)
    overview = TrendOverview(
        signals=[
            TrendSignalOut(
                name="RAG",
                hotness=88,
                paper_count=12,
                month_over_month_change=0.25,
            )
        ],
        topics=[topic],
    )
    detail = TrendDetailOut(
        id=topic_id,
        name=topic.name,
        monthly_trend=[TrendMonthlyPoint(month="2026-07", count=12)],
        milestones=[
            TrendMilestone(
                paper_id="2401.00001",
                title="A milestone",
                significance="turning_point",
            )
        ],
        phases=[
            TrendPhase(
                phase="growing",
                start_month="2026-01",
                end_month="2026-07",
                description="Rapid growth",
            )
        ],
    )

    assert overview.topics[0].id == topic_id
    assert overview.signals[0].month_over_month_change == 0.25
    assert detail.monthly_trend[0].count == 12
    assert detail.milestones[0].citation_count == 0
    assert detail.phases[0].phase == "growing"
