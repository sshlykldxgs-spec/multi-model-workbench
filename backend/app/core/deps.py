"""依赖注入。把 GatewayService、注册表与策略挂在 app.state 上，便于测试替换。"""

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
