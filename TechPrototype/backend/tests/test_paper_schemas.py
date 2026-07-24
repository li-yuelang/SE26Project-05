"""Tests for paper schemas — validation & serialization."""

from uuid import uuid4

from app.schemas.paper import PaperDetail, PaperFilterParams, PaperListItem, PaperListResponse, PaperUpdateRequest


def test_paper_list_item_serialization():
    item = PaperListItem(
        id=uuid4(),
        arxiv_id="2406.01234",
        title="Test Paper",
        authors=["Alice"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        published_at=None,
        updated_at_source=None,
        abstract="Test abstract",
        parsed_status="pending",
        pdf_url="https://arxiv.org/pdf/2406.01234",
        arxiv_url="https://arxiv.org/abs/2406.01234",
    )
    d = item.model_dump(mode="json")
    assert d["arxiv_id"] == "2406.01234"
    assert d["title"] == "Test Paper"


def test_paper_detail_inherits_list_item():
    item = PaperDetail(
        id=uuid4(),
        arxiv_id="2406.01234",
        title="Test",
        authors=["Alice"],
        categories=["cs.AI"],
        primary_category="cs.AI",
        published_at=None,
        updated_at_source=None,
        abstract="Test",
        parsed_status="pending",
        pdf_url="",
        arxiv_url="",
        source_content=None,
        structured_content=None,
        metadata_extra=None,
        created_at="2026-07-01T00:00:00Z",
        updated_at="2026-07-01T00:00:00Z",
    )
    d = item.model_dump(mode="json")
    assert d["abstract"] == "Test"
    assert "created_at" in d
    assert "updated_at" in d


def test_paper_filter_params_defaults():
    p = PaperFilterParams()
    assert p.page == 1
    assert p.page_size == 20
    assert p.query is None


def test_paper_list_response_serialization():
    resp = PaperListResponse(items=[], total=0, page=1, page_size=20)
    d = resp.model_dump(by_alias=True)
    assert d["pageSize"] == 20


def test_paper_update_request_partial():
    r = PaperUpdateRequest(parsed_status="done")
    d = r.model_dump(exclude_none=True)
    assert d == {"parsed_status": "done"}
