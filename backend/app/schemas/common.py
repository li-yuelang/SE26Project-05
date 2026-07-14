from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    code: str = "OK"
    message: str = "success"
    data: T


class PageResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(populate_by_name=True)

    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100, serialization_alias="pageSize")


def success(data: T, message: str = "success") -> dict[str, Any]:
    return {"code": "OK", "message": message, "data": data}
