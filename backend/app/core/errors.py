"""统一错误格式。

契约（docs/api-contract.md 第 2 节）：错误码是封闭集合。
新增错误码必须同时改契约，否则门禁会拦下。
"""

from enum import StrEnum
from typing import Any

from fastapi import Request, status
from fastapi.responses import JSONResponse


class ErrorCode(StrEnum):
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    VALIDATION_FAILED = "validation_failed"
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMITED = "rate_limited"
    BUDGET_EXCEEDED = "budget_exceeded"
    RUN_CONFLICT = "run_conflict"
    TOOL_DENIED = "tool_denied"
    INTERNAL_ERROR = "internal_error"


#: 每个错误码的 HTTP 状态。用字面量而不是 starlette 的常量：
#: 实测 starlette 1.7.0 已把 HTTP_422_UNPROCESSABLE_ENTITY 改名，
#: 而 pytest 配了 filterwarnings=error，弃用警告会直接变成测试失败。
#: 契约（docs/api-contract.md 第 2 节）里写的就是这些数字，两者必须一致。
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHORIZED: 401,
    ErrorCode.FORBIDDEN: 403,
    ErrorCode.NOT_FOUND: 404,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.MODEL_UNAVAILABLE: 502,
    ErrorCode.RATE_LIMITED: 429,
    ErrorCode.BUDGET_EXCEEDED: 402,
    ErrorCode.RUN_CONFLICT: 409,
    ErrorCode.TOOL_DENIED: 403,
    ErrorCode.INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    """业务异常。被全局 handler 转成统一错误格式。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        *,
        detail: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.detail = detail or {}


def _payload(code: ErrorCode, message: str, request_id: str, **extra: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "error": {"code": str(code), "message": message, "request_id": request_id}
    }
    if extra:
        body["error"]["detail"] = extra
    return body


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, ApiError)
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=HTTP_STATUS[exc.code],
        content=_payload(exc.code, exc.message, request_id, **exc.detail),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """未预期错误一律转 internal_error，不泄漏栈信息给前端。"""
    request_id = getattr(request.state, "request_id", "")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_payload(ErrorCode.INTERNAL_ERROR, "服务器内部错误", request_id),
    )
