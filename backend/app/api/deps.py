"""API 层的依赖注入。

**为什么在 api 层而不是 core**：本模块是「组装根」，它同时 import 了
gateway（取网关与注册表）与 middleware.policies（取策略接口）。
若放在 app/core/ 下，core 就会反向依赖 middleware ——
实测被分层门禁判为「下层依赖上层」。
core 应当是最底层的基础设施（配置、日志、错误），不含组装逻辑。
"""

from fastapi import Request

from app.gateway.registry import AdapterRegistry
from app.gateway.service import GatewayService
from app.middleware.policies.base import (
    BudgetPolicy,
    ContentPolicy,
    RateLimitPolicy,
    RoutingPolicy,
)


def get_gateway(request: Request) -> GatewayService:
    return request.app.state.gateway  # type: ignore[no-any-return]


def get_registry(request: Request) -> AdapterRegistry:
    return request.app.state.registry  # type: ignore[no-any-return]


def get_budget_policy(request: Request) -> BudgetPolicy:
    return request.app.state.budget_policy  # type: ignore[no-any-return]


def get_rate_limit_policy(request: Request) -> RateLimitPolicy:
    return request.app.state.rate_limit_policy  # type: ignore[no-any-return]


def get_content_policy(request: Request) -> ContentPolicy:
    return request.app.state.content_policy  # type: ignore[no-any-return]


def get_routing_policy(request: Request) -> RoutingPolicy:
    return request.app.state.routing_policy  # type: ignore[no-any-return]
