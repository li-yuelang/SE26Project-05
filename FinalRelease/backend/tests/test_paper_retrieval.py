from types import SimpleNamespace

from app.services.paper_retrieval import (
    PaperHybridRetriever,
    calculate_hybrid_score,
    calculate_lexical_relevance,
)


def make_paper(**overrides):
    values = {
        "title": "Efficient Transformers for Long Documents",
        "abstract": "We introduce a sparse attention method.",
        "primary_category": "cs.CL",
        "categories": ["cs.CL", "cs.AI"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_lexical_relevance_uses_title_abstract_and_category() -> None:
    score, matched = calculate_lexical_relevance(
        make_paper(),
        ["transformers", "sparse attention", "cs.ai"],
    )

    assert score == 0.6667
    assert matched == ["transformers", "sparse attention", "cs.ai"]


def test_hybrid_score_rewards_semantic_similarity() -> None:
    lexical_only = calculate_hybrid_score(0.5, None, 1.0)
    hybrid = calculate_hybrid_score(0.5, 0.9, 1.0)

    assert lexical_only == 0.6
    assert hybrid == 0.75


def test_hybrid_score_falls_back_without_vectors() -> None:
    assert calculate_hybrid_score(0.85, None, 1.0) == 0.88


def test_reason_explains_retrieval_signals() -> None:
    reason = PaperHybridRetriever._build_reason(
        ["transformer"],
        0.82,
        "基于你最近阅读的论文",
    )

    assert "最近阅读" in reason
    assert "命中主题条件" in reason
    assert "语义相似" in reason
    assert "发布时间" in reason
