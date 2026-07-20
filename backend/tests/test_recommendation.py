"""Tests for RecommendationService — serialisation helper."""

from types import SimpleNamespace
from uuid import uuid4

from app.services.recommendation import RecommendationService


def _make_paper(**kwargs):
    return SimpleNamespace(
        id=kwargs.get("id", uuid4()),
        arxiv_id=kwargs.get("arxiv_id", "2401.00001"),
        title=kwargs.get("title", "A Paper"),
        authors=kwargs.get("authors", ["Author"]),
        abstract=kwargs.get("abstract", "Abstract text"),
        primary_category=kwargs.get("primary_category", "cs.AI"),
    )


class TestRecommendationSerialisation:
    def test_serialise_recommendation_returns_expected_shape(self):
        paper = _make_paper()
        result = RecommendationService._serialise_recommendation(
            paper, 0.85, "与你最近阅读领域相关"
        )
        assert result["paper_id"] == str(paper.id)
        assert result["arxiv_id"] == paper.arxiv_id
        assert result["title"] == paper.title
        assert result["relevance_score"] == 0.85
        assert result["reason"] == "与你最近阅读领域相关"
        assert isinstance(result["authors"], list)
        assert "abstract" in result
        assert "primary_category" in result

    def test_serialise_recommendation_handles_none_fields(self):
        paper = _make_paper(authors=None, abstract=None, primary_category=None)
        result = RecommendationService._serialise_recommendation(
            paper, 0.5, "推荐理由"
        )
        assert result["authors"] == []
        assert result["abstract"] == ""
        assert result["primary_category"] == ""
