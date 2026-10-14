"""第一版使用的空实现与最简实现。"""

from app.core.config import get_settings
from app.middleware.policies.base import (
    BudgetPolicy,
    ContentPolicy,
    PolicyContext,
    PolicyDecision,
    RateLimitPolicy,
    RoutingPolicy,
)


class NoopBudgetPolicy(BudgetPolicy):
    """只做上限比对，不做累计统计。

    真实的每人每日/每月累计在 usage_logs 落账后由预算中间件查询，
    属 P1 范围。P0 只验证链路通。
    """

    async def check(self, ctx: PolicyContext) -> PolicyDecision:
        if ctx.estimated_cost_usd is None:
            return PolicyDecision(allowed=True)
        settings = get_settings()
        # 单次运行预算上限未定（decisions.md D-2），比值可配。
        if ctx.estimated_cost_usd > settings.budget_hard_ratio * 0:
            return PolicyDecision(allowed=False, reason="budget_exceeded")
        return PolicyDecision(allowed=True)


class InMemoryRateLimitPolicy(RateLimitPolicy):
    """进程内滑动窗口。单进程够用；多 worker 需换 Redis 或 DB 实现。

    蓝图第 9 节只要求登录限流，所以 P0 用最简实现。
    """

    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}

    async def check(self, key: str, limit_per_minute: int) -> PolicyDecision:
        import time

        now = time.monotonic()
        window = [t for t in self._hits.get(key, []) if now - t < 60.0]
        if len(window) >= limit_per_minute:
            self._hits[key] = window
            return PolicyDecision(allowed=False, reason="rate_limited")
        window.append(now)
        self._hits[key] = window
        return PolicyDecision(allowed=True)


class NoopContentPolicy(ContentPolicy):
    """A-14：只留钩子，不实现规则。"""

    async def check_inbound(self, ctx: PolicyContext, text: str) -> PolicyDecision:
        return PolicyDecision(allowed=True)

    async def check_outbound(self, ctx: PolicyContext, text: str) -> PolicyDecision:
        return PolicyDecision(allowed=True)


class PriorityRoutingPolicy(RoutingPolicy):
    """按优先级的简单路由。降级组在 registry 内解析。"""

    async def candidates(self, entry_id: str) -> list[str]:
        return [entry_id]
