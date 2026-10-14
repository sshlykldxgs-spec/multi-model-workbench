"""接入层与能力校验的单元测试（A-17、A-18）。"""

import pytest

from app.core.errors import ApiError
from app.gateway.base import Capability, ChatMessage, ModelEntry, Protocol
from app.gateway.registry import build_default_registry
from app.gateway.service import GatewayService


def _service(entries: list[ModelEntry]) -> GatewayService:
    return GatewayService(build_default_registry({"openai": "sk-test"}, entries))


def test_cost_uses_entry_price_not_model_name() -> None:
    """单价挂条目上：中转与官方价格不同（A-12 ⑤）。"""
    svc = _service([])
    from app.gateway.base import Usage

    cheap = ModelEntry(id="a", protocol=Protocol.OPENAI_COMPAT, model="gpt-4o",
                       input_price_per_mtok=1.0, output_price_per_mtok=2.0)
    pricey = ModelEntry(id="b", protocol=Protocol.OPENAI_COMPAT, model="gpt-4o",
                        input_price_per_mtok=10.0, output_price_per_mtok=20.0)
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert svc.cost_usd(cheap, usage) == pytest.approx(3.0)
    assert svc.cost_usd(pricey, usage) == pytest.approx(30.0)


def test_capability_check_rejects_streaming_missing() -> None:
    """A-17：运行前校验，不做「跑一半才崩」。"""
    svc = _service([])
    entry = ModelEntry(id="x", protocol=Protocol.OPENAI_COMPAT, model="m", capabilities=set())
    with pytest.raises(ApiError) as exc:
        svc.check_capabilities(entry, [ChatMessage(role="user", content="hi")])
    assert exc.value.code == "model_unavailable"


def test_capability_check_rejects_tool_history_on_non_tool_model() -> None:
    """切换模型时提前报错，而不是静默截断历史（design.md 第 4 节）。"""
    svc = _service([])
    entry = ModelEntry(id="x", protocol=Protocol.OPENAI_COMPAT, model="m",
                       capabilities={Capability.STREAMING})
    messages = [
        ChatMessage(role="user", content="查天气"),
        ChatMessage(role="tool", content="晴", tool_call_id="t1"),
    ]
    with pytest.raises(ApiError) as exc:
        svc.check_capabilities(entry, messages)
    assert exc.value.code == "model_unavailable"
    assert "工具调用" in exc.value.message


def test_base_url_normalized_to_v1() -> None:
    """design.md 12.8.4：base_url 必须以 /v1 结尾且无尾部斜杠。"""
    from app.gateway.protocols.openai_compat import _normalize_base_url

    assert _normalize_base_url("https://relay.example.com") == "https://relay.example.com/v1"
    assert _normalize_base_url("https://relay.example.com/") == "https://relay.example.com/v1"
    assert _normalize_base_url("https://relay.example.com/v1") == "https://relay.example.com/v1"
    assert _normalize_base_url("https://relay.example.com/v1/") == "https://relay.example.com/v1"
    assert _normalize_base_url(None) is None
