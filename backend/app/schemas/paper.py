from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PaperAuthorList(list[str]):
    """Authors as a list of strings."""


# ── 列表 & 搜索 ──────────────────────────────────────────────

class PaperFilterParams(BaseModel):
    query: str | None = Field(default=None, max_length=500, description="全文搜索关键词")
    category: str | None = Field(default=None, max_length=100, description="按主分类筛选")
    author: str | None = Field(default=None, max_length=200, description="按作者筛选")
    status: str | None = Field(default=None, max_length=32, description="按解析状态筛选")
    parsed_status: str | None = Field(default=None, max_length=32, description="按解析状态筛选")
    date_from: str | None = Field(default=None, description="发表日期起始 (YYYY-MM-DD)")
    date_to: str | None = Field(default=None, description="发表日期截止 (YYYY-MM-DD)")
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaperListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    arxiv_id: str
    title: str
    authors: list[str]
    categories: list[str]
    primary_category: str | None
    published_at: datetime | None
    updated_at_source: datetime | None
    abstract: str
    parsed_status: str
    pdf_url: str
    arxiv_url: str


class PaperListResponse(BaseModel):
    items: list[PaperListItem]
    total: int
    page: int
    page_size: int = Field(serialization_alias="pageSize")


# ── 详情 ─────────────────────────────────────────────────────

class PaperDetail(PaperListItem):
    model_config = ConfigDict(from_attributes=True)

    source_content: str | None
    structured_content: dict | None
    metadata_extra: dict | None
    created_at: datetime
    updated_at: datetime


# ── 更新 ─────────────────────────────────────────────────────

class PaperUpdateRequest(BaseModel):
    parsed_status: str | None = Field(default=None, max_length=32)
    structured_content: dict | None = None
    source_content: str | None = None
