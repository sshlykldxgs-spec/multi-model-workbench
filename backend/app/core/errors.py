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


#: 每个错误码的 HTTP 状态。前端为每个码准备人话提示（frontend/AGENTS.md 第 6 节）。
HTTP_STATUS: dict[ErrorCode, int] = {
    ErrorCode.UNAUTHORIZED: status.HTTP_401_UNAUTHORIZED,
    ErrorCode.FORBIDDEN: status.HTTP_403_FORBIDDEN,
    ErrorCode.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    ErrorCode.VALIDATION_FAILED: status.HTTP_422_UNPROCESSABLE_ENTITY,
    ErrorCode.MODEL_UNAVAILABLE: status.HTTP_502_BAD_GATEWAY,
    ErrorCode.RATE_LIMITED: status.HTTP_429_TOO_MANY_REQUESTS,
    ErrorCode.BUDGET_EXCEEDED: status.HTTP_402_PAYMENT_REQUIRED,
    ErrorCode.RUN_CONFLICT: status.HTTP_409_CONFLICT,
    ErrorCode.TOOL_DENIED: status.HTTP_403_FORBIDDEN,
    ErrorCode.INTERNAL_ERROR: status.HTTP_500_INTERNAL_SERVER_ERROR,
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
