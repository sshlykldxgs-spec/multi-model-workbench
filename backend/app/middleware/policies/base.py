"""策略点：固定接口 + 可替换实现。

A-15：第一版一律挂 Noop 或最简实现。将来加收费、封控、监管 = 换一个实现 + 改配置。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class PolicyContext:
    """策略决策所需的上下文。只读。"""

    user_id: str | None
    conversation_id: str | None
    run_id: str | None
    model_entry_id: str | None
    estimated_cost_usd: float | None


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    reason: str = ""


class BudgetPolicy(ABC):
    """预算策略。蓝图第 9 节：80% 告警、100% 中止。"""

    @abstractmethod
    async def check(self, ctx: PolicyContext) -> PolicyDecision: ...


class RateLimitPolicy(ABC):
    """限流策略。登录限流与模型调用限流都走这里。"""

    @abstractmethod
    async def check(self, key: str, limit_per_minute: int) -> PolicyDecision: ...


class ContentPolicy(ABC):
    """内容策略：入站与出站两个钩子。

    A-14：第一版空实现，只留钩子。监管与内容审核将来挂在这里。
    """

    @abstractmethod
    async def check_inbound(self, ctx: PolicyContext, text: str) -> PolicyDecision: ...

    @abstractmethod
    async def check_outbound(self, ctx: PolicyContext, text: str) -> PolicyDecision: ...


class RoutingPolicy(ABC):
    """路由策略。A-12：官方与中转双线，可降级。

    A-18：降级必须在事件流中告知用户，不得静默换模型。
    """

    @abstractmethod
    async def candidates(self, entry_id: str) -> list[str]: ...
