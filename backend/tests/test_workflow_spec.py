"""发布前校验（design.md 7.4）。"""

from app.orchestrator.workflow import TemplateKind, WorkflowSpec, validate_spec


def test_rejects_empty_roles() -> None:
    spec = WorkflowSpec(name="w", template=TemplateKind.SEQUENTIAL, roles=[], budget_usd=5.0)
    assert any("角色" in p for p in validate_spec(spec, set(), set()))


def test_rejects_missing_budget() -> None:
    spec = WorkflowSpec(name="w", template=TemplateKind.SEQUENTIAL, roles=["planner"])
    assert any("预算" in p for p in validate_spec(spec, set(), set()))


def test_rejects_zero_max_rounds() -> None:
    spec = WorkflowSpec(
        name="w", template=TemplateKind.SEQUENTIAL, roles=["planner"], max_rounds=0, budget_usd=5.0
    )
    assert any("轮数" in p for p in validate_spec(spec, set(), set()))


def test_group_chat_warns_on_large_rounds() -> None:
    """群聊最容易失控（蓝图第 12 节第 3 项）。"""
    spec = WorkflowSpec(
        name="w", template=TemplateKind.GROUP_CHAT, roles=["a"], max_rounds=20, budget_usd=5.0
    )
    assert any("群聊" in p for p in validate_spec(spec, set(), set()))


def test_valid_spec_passes() -> None:
    spec = WorkflowSpec(
        name="w", template=TemplateKind.SEQUENTIAL, roles=["planner"], budget_usd=5.0
    )
    assert validate_spec(spec, set(), set()) == []
