from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class TaskLogItem(BaseModel):
    time: str
    level: str
    content: str


class TaskPaperItem(BaseModel):
    id: str
    title: str
    category: str | None = None
    published: str | None = None
    status: str | None = Field(default=None, description="论文入库状态")


class FetchTaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_type: str
    status: str
    schedule: str | None
    keywords: list[str]
    categories: list[str] | None
    execution_log: list[dict]
    started_at: datetime | None
    finished_at: datetime | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskCatalogResponse(BaseModel):
    status_meta: dict = Field(default_factory=lambda: {
        "running": {"label": "运行中", "color": "processing", "tag_color": "blue"},
        "scheduled": {"label": "已计划", "color": "default", "tag_color": "default"},
        "paused": {"label": "已暂停", "color": "warning", "tag_color": "orange"},
        "failed": {"label": "失败", "color": "error", "tag_color": "red"},
        "completed": {"label": "已完成", "color": "success", "tag_color": "green"},
    }, serialization_alias="statusMeta")
    type_meta: dict = Field(default_factory=lambda: {
        "category": "分类订阅",
        "keyword": "关键词检索",
        "author": "作者追踪",
        "citation": "引用扩展",
    }, serialization_alias="typeMeta")
    tasks: list[FetchTaskResponse]
    total: int


class TaskUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=32)
    schedule: str | None = Field(default=None, max_length=100)
    keywords: list[str] | None = None
    categories: list[str] | None = None
