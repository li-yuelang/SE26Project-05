"""Tests for common schemas — ApiResponse, PageResponse, success()."""

from app.schemas.common import ApiResponse, PageResponse, success


def test_api_response_default_code_and_message() -> None:
    resp = ApiResponse[dict](data={"key": "value"})
    assert resp.code == "OK"
    assert resp.message == "success"
    assert resp.data == {"key": "value"}


def test_success_helper() -> None:
    result = success({"items": [1, 2]})
    assert result["code"] == "OK"
    assert result["message"] == "success"
    assert result["data"] == {"items": [1, 2]}


def test_success_with_custom_message() -> None:
    result = success("done", message="操作成功")
    assert result["message"] == "操作成功"


def test_page_response_snake_case_field_access() -> None:
    resp = PageResponse[str](items=["a", "b"], total=2, page=1, page_size=10)
    assert resp.items == ["a", "b"]
    assert resp.total == 2
    assert resp.page == 1
    assert resp.page_size == 10


def test_page_response_camel_case_alias() -> None:
    resp = PageResponse[str](items=[], total=0, page=1, page_size=20)
    dumped = resp.model_dump(by_alias=True)
    assert dumped["pageSize"] == 20
    assert dumped["page"] == 1


def test_page_response_defaults() -> None:
    resp = PageResponse[str]()
    assert resp.items == []
    assert resp.total == 0
    assert resp.page == 1
    assert resp.page_size == 20
