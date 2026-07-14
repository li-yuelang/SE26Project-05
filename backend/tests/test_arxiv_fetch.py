"""Tests for arXiv fetch service — no network calls, pure XML parsing."""
from app.services.arxiv_fetch import build_search_query


class TestBuildSearchQuery:
    def test_keywords_only(self):
        q = build_search_query(keywords=["transformer", "attention"])
        assert 'all:"transformer"' in q
        assert 'all:"attention"' in q
        assert "AND" in q

    def test_categories_only(self):
        q = build_search_query(categories=["cs.CL", "cs.AI"])
        assert "cat:cs.CL" in q
        assert "cat:cs.AI" in q
        assert "OR" in q

    def test_author(self):
        q = build_search_query(author="lecun")
        assert 'au:"lecun"' in q

    def test_title_words(self):
        q = build_search_query(title_words=["retrieval", "augmented"])
        assert 'ti:"retrieval"' in q
        assert 'ti:"augmented"' in q

    def test_combined(self):
        q = build_search_query(keywords=["RAG"], categories=["cs.IR"], author="smith")
        assert 'all:"RAG"' in q
        assert "cat:cs.IR" in q
        assert 'au:"smith"' in q
        assert q.count("AND") >= 2

    def test_empty(self):
        q = build_search_query()
        assert q == "*"
