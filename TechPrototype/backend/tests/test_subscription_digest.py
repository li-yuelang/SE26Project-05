from types import SimpleNamespace

from app.api.v1.subscriptions import _calculate_digest_relevance


def make_paper(**overrides):
    values = {
        "title": "Efficient Transformers for Long Documents",
        "abstract": "We introduce a sparse attention method.",
        "primary_category": "cs.CL",
        "categories": ["cs.CL", "cs.AI"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_digest_relevance_rewards_title_matches() -> None:
    score, matched = _calculate_digest_relevance(make_paper(), ["transformers"])

    assert score == 0.85
    assert matched == ["transformers"]


def test_digest_relevance_scores_abstract_and_category_matches() -> None:
    abstract_score, _ = _calculate_digest_relevance(make_paper(), ["sparse attention"])
    category_score, matched = _calculate_digest_relevance(make_paper(), ["cs.ai"])

    assert abstract_score == 0.5
    assert category_score == 0.65
    assert matched == ["cs.ai"]


def test_digest_relevance_returns_zero_without_terms() -> None:
    assert _calculate_digest_relevance(make_paper(), []) == (0.0, [])
