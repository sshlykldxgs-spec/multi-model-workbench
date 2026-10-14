"""应用入口。

启动顺序很重要（design.md 12.8.1）：
  load_dotenv() 必须在 configure_otel_providers() 之前 ——
  provider 只在创建时读一次环境变量。
"""

import os

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from app.api.v1 import api_router
from app.core.config import get_settings
from app.core.errors import (
    ApiError,
    ErrorCode,
    api_error_handler,
    unhandled_error_handler,
)
from app.core.logging import configure_logging
from app.gateway.registry import build_default_registry
from app.gateway.service import GatewayService
from app.middleware.chain import RequestIdMiddleware
from app.middleware.policies.noop import (
    InMemoryRateLimitPolicy,
    NoopBudgetPolicy,
    NoopContentPolicy,
    PriorityRoutingPolicy,
)
from app.models.base import Base
from app.orchestrator.observability import configure_observability
from app.schemas.auth import CurrentUser


def _load_env_before_otel() -> None:
    """显式加载 .env。MAF 不会自动读 .env（蓝图与 design.md 12.8.4 都提醒过）。"""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


#: P0 引导管理员的固定 ID。
#: get_current_user 用它到 app.state.bootstrap_users 里查真实身份。
#: P1 接入 users 表后，本常量与 bootstrap_users 一起移除。
BOOTSTRAP_ADMIN_ID = "bootstrap-admin"


def create_app() -> FastAPI:
    _load_env_before_otel()
    settings = get_settings()
    configure_logging("DEBUG" if settings.debug else "INFO")
    configure_observability(settings)

    from app.api.v1.models import default_entries

    app = FastAPI(
        title=settings.app_name,
        version="0.0.1",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # --- 模型接入层 ---
    entries = default_entries()
    credentials: dict[str, str] = {
        "openai": os.environ.get("OPENAI_API_KEY", ""),
        "anthropic": os.environ.get("ANTHROPIC_API_KEY", ""),
        "gemini": os.environ.get("GEMINI_API_KEY", ""),
        "relay": os.environ.get("RELAY_API_KEY", ""),
    }
    registry = build_default_registry(credentials, entries)
    app.state.registry = registry
    app.state.gateway = GatewayService(registry)
    app.state.model_entries = entries

    # --- 策略点（A-15：第一版挂 Noop 或最简实现）---
    app.state.budget_policy = NoopBudgetPolicy()
    app.state.rate_limit_policy = InMemoryRateLimitPolicy()
    app.state.content_policy = NoopContentPolicy()
    app.state.routing_policy = PriorityRoutingPolicy()

    # --- P0 引导管理员（P1 接入 users 表后移除）---
    from app.api.v1.auth import hash_password
    from app.models.enums import UserRole

    app.state.bootstrap_admin_email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
    app.state.bootstrap_admin_hash = hash_password(
        os.environ.get("BOOTSTRAP_ADMIN_PASSWORD", "admin12345")
    )
    app.state.bootstrap_admin_role = UserRole.ADMIN
    # P0 的用户目录。get_current_user 从这里取真实角色，
    # 而不是硬编码 —— 否则管理员登录后会被识别成成员。
    app.state.bootstrap_users = {
        BOOTSTRAP_ADMIN_ID: CurrentUser(
            id=BOOTSTRAP_ADMIN_ID,
            email=app.state.bootstrap_admin_email,
            role=UserRole.ADMIN,
        )
    }

    # --- 中间件 ---
    app.add_middleware(RequestIdMiddleware)

    # --- 错误处理：统一格式 ---
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(Exception, unhandled_error_handler)

    async def _validation_handler(request, exc):  # type: ignore[no-untyped-def]
        from fastapi.responses import JSONResponse

        request_id = getattr(request.state, "request_id", "")
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": str(ErrorCode.VALIDATION_FAILED),
                    "message": "参数校验失败",
                    "request_id": request_id,
                    "detail": {"errors": exc.errors()[:10]},
                }
            },
        )

    app.add_exception_handler(RequestValidationError, _validation_handler)

    app.include_router(api_router)

    # 让 ORM 元数据在被导入时注册（P1 起 alembic 用）
    _ = Base.metadata

    return app


app = create_app()
