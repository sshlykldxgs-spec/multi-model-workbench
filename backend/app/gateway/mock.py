"""Mock 模型。供前端联调与自动测试使用（蓝图 5.2）。

P0 验收要求：选 mock 模型发一句话，看到逐字输出。
所以它必须真的逐字流式吐字，而不是一次返回整段。
"""

import asyncio
from collections.abc import AsyncIterator

from app.gateway.base import (
    Capability,
    ChatChunk,
    ChatMessage,
    ChatRequest,
    ModelEntry,
    Protocol,
    ProviderAdapter,
    Usage,
)


class MockAdapter(ProviderAdapter):
    protocol = Protocol.OPENAI_COMPAT

    def supports(self, entry: ModelEntry) -> bool:
        return entry.id.startswith("mock")

    def _reply(self, messages: list[ChatMessage]) -> str:
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        asked = last_user.content if last_user else ""
        return (
            f"（mock 模型）我收到了你的消息：「{asked}」。\n\n"
            "这是 P0 阶段的占位回复，用于验证流式链路。"
            "接入真实模型后，这里会换成真正的回答。"
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        reply = self._reply(req.messages)
        # 逐字吐出，模拟真实流式的节奏，让前端的逐字渲染能被真正验证。
        step = 2
        for i in range(0, len(reply), step):
            await asyncio.sleep(0.02)
            yield ChatChunk(text=reply[i : i + step])
        yield ChatChunk(
            done=True,
            usage=Usage(
                input_tokens=sum(len(m.content) for m in req.messages) // 2,
                output_tokens=len(reply) // 2,
                upstream_model=req.model_entry.model,
            ),
        )

    async def probe_capabilities(self, entry: ModelEntry) -> set[Capability]:
        return {Capability.STREAMING}
