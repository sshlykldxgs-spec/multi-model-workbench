"""GatewayService：业务代码唯一入口。

R-3 的落地：路由与编排层只调这里，不碰适配器与厂商 SDK。
本层负责能力校验（A-17）、降级（A-18）与用量折算。
"""

from collections.abc import AsyncIterator

from app.core.errors import ApiError, ErrorCode
from app.gateway.base import (
    Capability,
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ModelEntry,
    Usage,
)
from app.gateway.registry import AdapterRegistry


class GatewayService:
    def __init__(self, registry: AdapterRegistry) -> None:
        self._registry = registry

    def cost_usd(self, entry: ModelEntry, usage: Usage) -> float:
        """按条目单价折算。单价挂条目上，因为中转与官方价格不同（A-12 ⑤）。"""
        return (
            usage.input_tokens * entry.input_price_per_mtok
            + usage.output_tokens * entry.output_price_per_mtok
        ) / 1_000_000

    def check_capabilities(
        self, entry: ModelEntry, messages: list[ChatMessage], *, need_stream: bool = True
    ) -> None:
        """运行前校验，不做「跑一半才崩」（A-17）。

        中途切换模型时同样走这里 —— 目标模型不支持工具调用而历史里有工具消息，
        就提前报错并建议开新会话，而不是静默截断（design.md 第 4 节）。
        """
        if need_stream and Capability.STREAMING not in entry.capabilities:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"条目 {entry.provider_label or entry.id} 未声明流式能力，无法用于对话",
            )
        has_tool_messages = any(m.role == "tool" for m in messages)
        if has_tool_messages and Capability.TOOL_CALLING not in entry.capabilities:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                "该会话历史包含工具调用消息，但目标模型不支持工具调用。"
                "请选择支持工具调用的模型，或开始一个新会话。",
            )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        entry = req.model_entry
        if not entry.enabled:
            raise ApiError(ErrorCode.MODEL_UNAVAILABLE, f"条目 {entry.id} 已停用")
        self.check_capabilities(entry, req.messages)
        adapter = self._registry.resolve(entry)
        async for chunk in adapter.stream_chat(req):
            yield chunk

    async def stream_with_fallback(
        self, req: ChatRequest, fallbacks: list[ModelEntry]
    ) -> AsyncIterator[ChatChunk]:
        """降级链。A-18：降级必须告知用户，绝不静默换模型。

        只在首个片段之前降级 —— 已经产生输出再换模型会让用户看到两段拼接的内容。
        """
        attempted: list[str] = []
        for entry in [req.model_entry, *fallbacks]:
            attempted.append(entry.provider_label or entry.id)
            emitted = False
            try:
                async for chunk in self.stream_chat(
                    ChatRequest(
                        messages=req.messages,
                        model_entry=entry,
                        temperature=req.temperature,
                        max_tokens=req.max_tokens,
                        tools=req.tools,
                        idempotency_key=req.idempotency_key,
                    )
                ):
                    if not emitted:
                        emitted = True
                        if len(attempted) > 1:
                            yield ChatChunk(
                                fallback_from=attempted[-2],
                                text="",
                            )
                    yield chunk
                return
            except ApiError:
                if emitted:
                    raise  # 已产出内容，不能中途换模型
                continue
        raise ApiError(
            ErrorCode.MODEL_UNAVAILABLE,
            f"全部候选条目均不可用（已尝试 {'、'.join(attempted)}）",
        )
