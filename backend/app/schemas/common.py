"""通用出入参。契约见 docs/api-contract.md 第 1 节。"""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """游标分页。契约约定：列表用游标分页。"""

    items: list[T]
    next_cursor: str | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    detail: dict | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class OkResponse(BaseModel):
    ok: bool = True


class CursorQuery(BaseModel):
    cursor: str | None = None
    limit: int = Field(default=50, ge=1, le=200)
