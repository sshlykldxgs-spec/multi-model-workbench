"""中间件：请求 ID 与审计。

审计是蓝图第 8 节的硬要求，所以 P0 就要真做（不是留位）。
"""

import uuid
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.logging import sanitize

REQUEST_ID_HEADER = "X-Request-ID"


class RequestIdMiddleware(BaseHTTPMiddleware):
    """为每个请求分配 request_id，贯穿日志、错误响应与审计。"""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


#: 需要审计的动作。蓝图第 8 节：登录、工具审批、文件上传与删除、配置变更。
AUDITED_ACTIONS: dict[tuple[str, str], str] = {
    ("POST", "/api/v1/auth/login"): "auth.login",
    ("POST", "/api/v1/auth/logout"): "auth.logout",
}


def audit_action_for(method: str, path: str) -> str | None:
    """把请求映射到审计动作名。

    写审计日志是副作用，放在路由里而不是中间件里，
    以便带上动作结果（成功/失败）与对象 ID。
    """
    if (action := AUDITED_ACTIONS.get((method, path))) is not None:
        return action
    if method in {"POST", "PATCH", "PUT", "DELETE"}:
        if "/knowledge-bases/" in path and "/documents" in path:
            return "document.write"
        if "/approvals/" in path:
            return "tool.approval"
        if path.startswith("/api/v1/studio/"):
            return "config.change"
        if path.startswith("/api/v1/admin/"):
            return "admin.change"
    return None


def audit_payload(**fields: object) -> dict[str, object]:
    """审计载荷一律脱敏（backend/AGENTS.md 第 10 节）。"""
    return sanitize(dict(fields))
