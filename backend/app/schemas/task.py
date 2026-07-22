"""Request and response contracts for user-owned arXiv fetch tasks."""

from __future__ import annotations

import re
from datetime import datetime, time
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

TASK_TYPES = ("keyword", "category")
SCHEDULE_KINDS = ("manual", "daily", "weekly")
KEYWORD_MATCH_MODES = ("or", "and")
LOOKBACK_DAYS = (1, 3, 7, 30)
TIMEZONE = "Asia/Shanghai"

# This is intentionally a compact catalog for the first version.  The API also
# accepts valid arXiv category-shaped values so newly added subcategories do
# not require an application release.
ARXIV_CATEGORY_OPTIONS = [
    {"value": "cs.AI", "label": "人工智能"},
    {"value": "cs.CL", "label": "计算语言学"},
    {"value": "cs.CV", "label": "计算机视觉"},
    {"value": "cs.IR", "label": "信息检索"},
    {"value": "cs.LG", "label": "机器学习"},
    {"value": "cs.SE", "label": "软件工程"},
    {"value": "cs.HC", "label": "人机交互"},
    {"value": "cs.RO", "label": "机器人"},
    {"value": "cs.DS", "label": "数据结构与算法"},
    {"value": "cs.NE", "label": "神经与进化计算"},
    {"value": "math.OC", "label": "优化与控制"},
    {"value": "math.ST", "label": "统计理论"},
    {"value": "stat.ML", "label": "统计机器学习"},
    {"value": "eess.SY", "label": "系统与控制"},
    {"value": "physics.comp-ph", "label": "计算物理"},
]

_CATEGORY_PREFIXES = {
    "astro-ph",
    "cond-mat",
    "cs",
    "econ",
    "eess",
    "gr-qc",
    "hep-ex",
    "hep-lat",
    "hep-ph",
    "hep-th",
    "math",
    "nlin",
    "nucl-ex",
    "nucl-th",
    "physics",
    "q-bio",
    "q-fin",
    "quant-ph",
    "stat",
}


def _dedupe_strings(value: list[str] | None, *, lower: bool = False) -> list[str]:
    if not value:
        return []
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned.lower() if lower else cleaned)
    return result


def is_valid_arxiv_category(category: str) -> bool:
    value = category.strip()
    if not value or value.count(".") != 1:
        return False
    prefix, suffix = value.split(".", 1)
    return prefix in _CATEGORY_PREFIXES and bool(re.fullmatch(r"[A-Za-z0-9-]+", suffix))


def validate_task_configuration(
    *,
    task_type: str,
    keywords: list[str],
    categories: list[str],
    keyword_match_mode: str,
    schedule_kind: str,
    schedule_time: time | None,
    schedule_weekday: int | None,
    timezone: str,
    initial_lookback_days: int,
    max_results: int,
) -> None:
    if task_type not in TASK_TYPES:
        raise ValueError(f"task_type must be one of: {', '.join(TASK_TYPES)}")
    if keyword_match_mode not in KEYWORD_MATCH_MODES:
        raise ValueError("keyword_match_mode must be 'or' or 'and'")
    if task_type == "keyword" and not 1 <= len(keywords) <= 10:
        raise ValueError("keyword tasks require 1 to 10 keywords")
    if task_type == "category" and not categories:
        raise ValueError("category tasks require at least one category")
    invalid_categories = [category for category in categories if not is_valid_arxiv_category(category)]
    if invalid_categories:
        raise ValueError(f"invalid arXiv categories: {', '.join(invalid_categories)}")
    if schedule_kind not in SCHEDULE_KINDS:
        raise ValueError(f"schedule_kind must be one of: {', '.join(SCHEDULE_KINDS)}")
    if schedule_kind == "manual" and (schedule_time is not None or schedule_weekday is not None):
        raise ValueError("manual schedules must not include schedule_time or schedule_weekday")
    if schedule_kind == "daily" and schedule_time is None:
        raise ValueError("daily schedules require schedule_time")
    if schedule_kind == "weekly" and (schedule_time is None or schedule_weekday is None):
        raise ValueError("weekly schedules require schedule_time and schedule_weekday")
    if schedule_weekday is not None and not 1 <= schedule_weekday <= 7:
        raise ValueError("schedule_weekday must be between 1 and 7")
    if timezone != TIMEZONE:
        raise ValueError(f"timezone must be {TIMEZONE}")
    if initial_lookback_days not in LOOKBACK_DAYS:
        raise ValueError(f"initial_lookback_days must be one of {LOOKBACK_DAYS}")
    if not 10 <= max_results <= 200:
        raise ValueError("max_results must be between 10 and 200")


class TaskLogItem(BaseModel):
    time: str
    level: str
    content: str


class TaskConfigRequest(BaseModel):
    """The durable task configuration shared by create and update requests."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    task_type: str = Field(default="keyword", max_length=32)
    keywords: list[str] = Field(default_factory=list, max_length=10)
    keyword_match_mode: str = Field(default="or", max_length=8)
    categories: list[str] = Field(default_factory=list, max_length=20)
    schedule_kind: str = Field(default="manual", max_length=16)
    schedule_time: time | None = None
    schedule_weekday: int | None = Field(default=None, ge=1, le=7)
    timezone: str = Field(default=TIMEZONE, max_length=64)
    is_enabled: bool = True
    initial_lookback_days: int = 7
    max_results: int = 50
    auto_analyze: bool = False

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: list[str] | None) -> list[str]:
        return _dedupe_strings(value, lower=False)

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: list[str] | None) -> list[str]:
        return _dedupe_strings(value, lower=False)

    @field_validator("keyword_match_mode", "task_type", "schedule_kind", mode="before")
    @classmethod
    def normalize_enums(cls, value: str | None) -> str | None:
        return value.strip().lower() if isinstance(value, str) else value

    @model_validator(mode="after")
    def validate_configuration(self) -> "TaskConfigRequest":
        validate_task_configuration(
            task_type=self.task_type,
            keywords=self.keywords,
            categories=self.categories,
            keyword_match_mode=self.keyword_match_mode,
            schedule_kind=self.schedule_kind,
            schedule_time=self.schedule_time,
            schedule_weekday=self.schedule_weekday,
            timezone=self.timezone,
            initial_lookback_days=self.initial_lookback_days,
            max_results=self.max_results,
        )
        return self


class TaskCreateRequest(TaskConfigRequest):
    run_now: bool = False


class TaskUpdateRequest(BaseModel):
    """Partial task update; ``status`` and ``schedule`` are legacy inputs."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    task_type: str | None = Field(default=None, max_length=32)
    keywords: list[str] | None = Field(default=None, max_length=10)
    keyword_match_mode: str | None = Field(default=None, max_length=8)
    categories: list[str] | None = Field(default=None, max_length=20)
    schedule_kind: str | None = Field(default=None, max_length=16)
    schedule_time: time | None = None
    schedule_weekday: int | None = Field(default=None, ge=1, le=7)
    timezone: str | None = Field(default=None, max_length=64)
    is_enabled: bool | None = None
    initial_lookback_days: int | None = None
    max_results: int | None = None
    auto_analyze: bool | None = None
    status: str | None = Field(default=None, max_length=32)
    schedule: str | None = Field(default=None, max_length=100)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        if not cleaned:
            raise ValueError("name must not be blank")
        return cleaned

    @field_validator("keywords", mode="before")
    @classmethod
    def normalize_keywords(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _dedupe_strings(value, lower=False)

    @field_validator("categories", mode="before")
    @classmethod
    def normalize_categories(cls, value: list[str] | None) -> list[str] | None:
        return None if value is None else _dedupe_strings(value, lower=False)

    @field_validator("keyword_match_mode", "task_type", "schedule_kind", mode="before")
    @classmethod
    def normalize_enums(cls, value: str | None) -> str | None:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("initial_lookback_days")
    @classmethod
    def validate_lookback(cls, value: int | None) -> int | None:
        if value is not None and value not in LOOKBACK_DAYS:
            raise ValueError(f"initial_lookback_days must be one of {LOOKBACK_DAYS}")
        return value

    @field_validator("max_results")
    @classmethod
    def validate_max_results(cls, value: int | None) -> int | None:
        if value is not None and not 10 <= value <= 200:
            raise ValueError("max_results must be between 10 and 200")
        return value


class FetchTaskResponse(BaseModel):
    """Task response with defaults retained for older schema consumers."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str = ""
    description: str | None = None
    task_type: str = "keyword"
    status: str = "scheduled"
    keywords: list[str] = Field(default_factory=list)
    keyword_match_mode: str = "or"
    categories: list[str] | None = Field(default_factory=list)
    schedule_kind: str = "manual"
    schedule_time: time | None = None
    schedule_weekday: int | None = None
    timezone: str = TIMEZONE
    is_enabled: bool = True
    next_run_at: datetime | None = None
    initial_lookback_days: int = 7
    max_results: int = 50
    auto_analyze: bool = False
    last_success_at: datetime | None = None
    candidate_count: int = 0
    new_count: int = 0
    duplicate_count: int = 0
    analysis_queued_count: int = 0
    analysis_enqueue_failed_count: int = 0
    page_count: int = 0
    schedule: str | None = None
    execution_log: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_message: str | None = None
    active_run_id: UUID | None = None
    latest_run_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaskSummary(BaseModel):
    running: int = 0
    scheduled: int = 0
    failed: int = 0
    new_papers: int = 0
    candidate_count: int = 0
    duplicate_count: int = 0


class TaskRunPaperResponse(BaseModel):
    id: UUID
    paper_id: UUID
    arxiv_id: str
    title: str
    primary_category: str | None = None
    published_at: datetime | None = None
    result_kind: str
    parsed_status: str


class FetchTaskRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    task_id: UUID
    trigger_kind: str
    config_snapshot: dict[str, Any] = Field(default_factory=dict)
    window_start: datetime | None = None
    window_end: datetime | None = None
    celery_task_id: str | None = None
    status: str
    candidate_count: int = 0
    new_count: int = 0
    duplicate_count: int = 0
    analysis_queued_count: int = 0
    analysis_enqueue_failed_count: int = 0
    page_count: int = 0
    execution_log: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    papers: list[TaskRunPaperResponse] = Field(default_factory=list)


class TaskCatalogResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    status_meta: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {
            "queued": {"label": "排队中", "color": "processing", "tag_color": "blue"},
            "running": {"label": "运行中", "color": "processing", "tag_color": "blue"},
            "scheduled": {"label": "已计划", "color": "default", "tag_color": "default"},
            "paused": {"label": "已暂停", "color": "warning", "tag_color": "orange"},
            "failed": {"label": "失败", "color": "error", "tag_color": "red"},
            "succeeded_with_warnings": {
                "label": "成功但有警告",
                "color": "warning",
                "tag_color": "orange",
            },
            "completed": {"label": "已完成", "color": "success", "tag_color": "green"},
        },
        serialization_alias="statusMeta",
    )
    type_meta: dict[str, str] = Field(
        default_factory=lambda: {"category": "分类检索", "keyword": "关键词检索"},
        serialization_alias="typeMeta",
    )
    items: list[FetchTaskResponse] = Field(default_factory=list)
    # Kept in the response for the original prototype's callers.
    tasks: list[FetchTaskResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, serialization_alias="pageSize")
    summary: TaskSummary = Field(default_factory=TaskSummary)

    @model_validator(mode="after")
    def synchronize_task_collections(self) -> "TaskCatalogResponse":
        """Keep the current ``items`` and legacy ``tasks`` fields equivalent."""

        if self.items and not self.tasks:
            self.tasks = list(self.items)
        elif self.tasks and not self.items:
            self.items = list(self.tasks)
        return self


class TaskDetailResponse(BaseModel):
    task: FetchTaskResponse
    summary: TaskSummary = Field(default_factory=TaskSummary)
    recent_runs: list[FetchTaskRunResponse] = Field(default_factory=list)
    status_meta: dict[str, dict[str, str]] = Field(default_factory=dict)
    type_meta: dict[str, str] = Field(default_factory=dict)


class TaskRunListResponse(BaseModel):
    items: list[FetchTaskRunResponse] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = Field(default=20, serialization_alias="pageSize")
