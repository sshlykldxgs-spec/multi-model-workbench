"""模型条目。GET /models 是 P0 验收要看的接口之一。

design.md 12.8.4：条目参数一律显式传入，绝不依赖环境变量推断端点。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_registry
from app.core.errors import ApiError, ErrorCode
from app.gateway.base import Capability, ModelEntry, Protocol
from app.gateway.registry import AdapterRegistry
from app.schemas.common import Page
from app.schemas.models import ModelInfo

router = APIRouter()


def _entry_to_info(entry: ModelEntry) -> ModelInfo:
    return ModelInfo(
        id=entry.id,
        protocol=str(entry.protocol),
        model=entry.model,
        provider_label=entry.provider_label,
        capabilities=sorted(str(c) for c in entry.capabilities),
        is_relay=entry.is_relay,
        enabled=entry.enabled,
    )


@router.get("/models")
async def list_models(request: Request) -> Page[ModelInfo]:
    entries: list[ModelEntry] = request.app.state.model_entries
    return Page[ModelInfo](items=[_entry_to_info(e) for e in entries if e.enabled])


@router.post("/admin/models")
async def create_model() -> dict[str, Any]:
    """P0 骨架：条目来自配置，暂不写库。

    P1 接入 models 表后改为真实 CRUD，并在写入时校验 base_url 以 /v1 结尾、
    校验 protocol 是封闭集合里的值。
    """
    return {"ok": True, "note": "P1 起接入 models 表"}


@router.post("/admin/models/{model_id}/test")
async def test_model(
    model_id: str,
    request: Request,
    registry: Annotated[AdapterRegistry, Depends(get_registry)],
) -> dict[str, Any]:
    entries: list[ModelEntry] = request.app.state.model_entries
    entry = next((e for e in entries if e.id == model_id), None)
    if entry is None:
        raise ApiError(ErrorCode.NOT_FOUND, f"模型条目 {model_id} 不存在")
    adapter = registry.resolve(entry)
    caps = await adapter.probe_capabilities(entry)
    return {
        "ok": True,
        "detail": "探测结果只作建议值，管理员必须可覆盖（中转站常谎报能力）",
        "detected_capabilities": sorted(str(c) for c in caps),
    }


def default_entries() -> list[ModelEntry]:
    """P0 默认条目：一个 mock（默认启用）+ 三家真实协议的占位（默认停用）。

    真实条目（含中转站 base_url 与凭据）由管理员在 P1 通过 models 表配置。
    默认停用是刻意的 —— P0 不该因为缺密钥而启动失败。
    """
    return [
        ModelEntry(
            id="mock-echo",
            protocol=Protocol.OPENAI_COMPAT,
            model="mock-echo",
            provider_label="Mock 模型",
            capabilities={Capability.STREAMING},
        ),
        ModelEntry(
            id="openai-gpt",
            protocol=Protocol.OPENAI_COMPAT,
            model="gpt-4o-mini",
            provider_label="OpenAI 官方",
            credential_ref="openai",
            capabilities={Capability.STREAMING, Capability.TOOL_CALLING},
            input_price_per_mtok=0.15,
            output_price_per_mtok=0.60,
            enabled=False,
        ),
        ModelEntry(
            id="relay-example",
            protocol=Protocol.OPENAI_COMPAT,
            model="gpt-4o-mini",
            base_url="https://relay.example.com/v1",
            provider_label="示例中转",
            credential_ref="relay",
            capabilities={Capability.STREAMING},
            is_relay=True,
            input_price_per_mtok=0.10,
            output_price_per_mtok=0.40,
            enabled=False,
        ),
        ModelEntry(
            id="anthropic-claude",
            protocol=Protocol.ANTHROPIC,
            model="claude-sonnet-5-5",
            provider_label="Anthropic 官方",
            credential_ref="anthropic",
            capabilities={Capability.STREAMING, Capability.TOOL_CALLING},
            enabled=False,
        ),
        ModelEntry(
            id="gemini-flash",
            protocol=Protocol.GEMINI,
            model="gemini-2.5-flash",
            provider_label="Google 官方",
            credential_ref="gemini",
            capabilities={Capability.STREAMING, Capability.TOOL_CALLING},
            enabled=False,
        ),
    ]
