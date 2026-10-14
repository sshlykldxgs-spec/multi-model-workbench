"""角色槽位与执行器（design.md 7.1、7.2）。

关键设计：角色是**槽位**不是模型。替换执行器不改工作流，
因为工作流只认槽位与统一输出格式。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Severity(StrEnum):
    BLOCKER = "blocker"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"


@dataclass
class ReviewIssue:
    severity: Severity
    message: str
    location: dict[str, Any] = field(default_factory=dict)
    suggestion: str = ""


@dataclass
class ReviewConclusion:
    """统一评审结论（design.md 7.2）。

    工作流只认这个格式。适配器负责把外部工具（OpenCodeReview 等）的输出转过来。
    外部工具无法给出的字段填空，**不得让格式差异渗透进工作流**。
    """

    passed: bool
    issues: list[ReviewIssue] = field(default_factory=list)
    summary: str = ""


@dataclass
class StepResult:
    ok: bool
    output: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoleSlot:
    """一个角色槽位。

    默认三角色由官方模板提供，但槽位本身可自由创建 —— 配置区可任意安排分工。
    """

    name: str
    role: str  # planner | worker | reviewer | 自定义
    instructions: str = ""
    executor_type: str = "model"
    #: 防「自己给自己打分」：Reviewer 与 Worker 必须不同模型或不同提示词（蓝图 5.1）。
    #: A-23：默认三角色分属三家厂商，天然满足这条。
    model_entry_id: str | None = None
    provider_label: str = ""
    allowed_tools: list[str] = field(default_factory=list)
    knowledge_base_ids: list[str] = field(default_factory=list)
    max_rounds: int = 2
    budget_usd: float | None = None


class RoleExecutor(ABC):
    """执行器抽象。槽位里可以换不同执行器，工作流不受影响。"""

    executor_type: str

    @abstractmethod
    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult: ...


class ModelAgentExecutor(RoleExecutor):
    """一个模型加一段指令。最常用的一种。"""

    executor_type = "model"

    def __init__(self, gateway: Any) -> None:
        self._gateway = gateway

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("P4 交付")


class ModelPanelExecutor(RoleExecutor):
    """多模型各审一遍再汇总（取交集或投票）。"""

    executor_type = "model_panel"

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("P4 交付（可选）")


class CliToolExecutor(RoleExecutor):
    """沙箱里跑命令行工具并解析输出。OpenCodeReview 走这里。

    已核实的接入点（design.md 12.4）：
        ocr review --format json --audience agent
    输出可稳定解析，适配器负责转成 ReviewConclusion。
    """

    executor_type = "cli_tool"

    def __init__(self, sandbox: Any) -> None:
        self._sandbox = sandbox

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("P4-A 交付")


class McpToolExecutor(RoleExecutor):
    """通过 MCP 调外部服务。"""

    executor_type = "mcp"

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("P2 之后交付")


class ExternalAgentExecutor(RoleExecutor):
    """A2A 外部 agent。蓝图列为「预留」。"""

    executor_type = "external_agent"

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("预留，第一版不实现")


class HumanExecutor(RoleExecutor):
    """暂停等待人工决定。审批与验收走这里。P2 接工具审批时先实化这一种。"""

    executor_type = "human"

    async def run(self, slot: RoleSlot, inputs: dict[str, Any]) -> StepResult:
        raise NotImplementedError("P2 交付")
