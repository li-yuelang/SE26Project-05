"""Tests for arXiv fetch service — no network calls, pure XML parsing."""

from datetime import datetime, timezone
import xml.etree.ElementTree as ET

from app.services.arxiv_fetch import _parse_entry, build_search_query


def test_entry_uses_arxiv_published_timestamp_not_updated_or_fetch_time():
    entry = ET.fromstring(
        """
        <entry xmlns="http://www.w3.org/2005/Atom">
          <id>http://arxiv.org/abs/2401.01234v3</id>
          <title>Publication date regression</title>
          <summary>Metadata must retain the original publication date.</summary>
          <published>2024-01-03T23:45:00Z</published>
          <updated>2026-07-22T08:30:00Z</updated>
          <author><name>Ada Lovelace</name></author>
          <category term="cs.SE" />
        </entry>
        """
    )

    paper = _parse_entry(entry)

    assert paper["published_at"] == datetime(2024, 1, 3, 23, 45, tzinfo=timezone.utc)
    assert paper["updated_at_source"] == datetime(2026, 7, 22, 8, 30, tzinfo=timezone.utc)
    assert paper["published_at"] != paper["updated_at_source"]


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
