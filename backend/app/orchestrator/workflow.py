"""工作流骨架（P4 交付主体）。

P0 只放接口与阶段划分，不建真实工作流 —— 因为工作流依赖模型接入、工具与知识库，
蓝图把多 agent 工作流放在最后（P4）正是这个原因。
"""

from dataclasses import dataclass, field
from enum import StrEnum


class TemplateKind(StrEnum):
    """蓝图 5.1：四种通用编排模板，MAF 1.0 已稳定支持。"""

    SEQUENTIAL = "sequential"
    CONCURRENT = "concurrent"
    HANDOFF = "handoff"
    GROUP_CHAT = "group_chat"


@dataclass
class WorkflowSpec:
    """一份分工定义。

    配置只决定「用什么、怎么分工」，**不授予权限**。
    工具审批、预算、知识库可见范围永远按运行者权限计算（design.md 7.4）。
    """

    name: str
    template: TemplateKind
    roles: list[str] = field(default_factory=list)
    max_rounds: int = 2
    budget_usd: float | None = None
    #: 蓝图：Planner 计划默认需要人工确认，可在编排里关闭。
    require_plan_approval: bool = True


def validate_spec(
    spec: WorkflowSpec, available_tools: set[str], available_kb: set[str]
) -> list[str]:
    """发布前校验（design.md 7.4）。

    返回问题清单，空列表表示通过。孤立节点、循环未设最大轮数、
    引用了不可用的模型/工具/知识库、未设预算上限 —— 都要拦下。
    """
    problems: list[str] = []
    if not spec.roles:
        problems.append("分工没有任何角色节点")
    if spec.max_rounds <= 0:
        problems.append("必须设置大于 0 的最大轮数（退回循环与群聊最容易失控）")
    if spec.budget_usd is None:
        problems.append("必须设置预算上限")
    if spec.template is TemplateKind.GROUP_CHAT and spec.max_rounds > 5:
        problems.append("群聊模板的轮数上限过大，建议不超过 5 轮")
    return problems
