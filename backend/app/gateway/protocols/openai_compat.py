"""OpenAI 兼容协议适配器。

覆盖：官方 OpenAI、Azure OpenAI、以及绝大多数第三方中转站与自建网关。

三个已核实的坑（design.md 12.8.4）：
  1. 默认用 chat.completions，不用 responses —— 多数中转站不支持 Responses API。
  2. base_url 必须以 /v1 结尾且不带尾部斜杠。
  3. 绝不依赖环境变量推断端点（Azure 与 OpenAI 变量并存时优先 OpenAI）。
"""

from collections.abc import AsyncIterator

from openai import AsyncOpenAI

from app.core.errors import ApiError, ErrorCode
from app.gateway.base import (
    Capability,
    ChatChunk,
    ChatRequest,
    ModelEntry,
    Protocol,
    ProviderAdapter,
    Usage,
)


def _normalize_base_url(url: str | None) -> str | None:
    """base_url 必须以 /v1 结尾且无尾部斜杠。"""
    if not url:
        return None
    cleaned = url.rstrip("/")
    if not cleaned.endswith("/v1"):
        cleaned = f"{cleaned}/v1"
    return cleaned


class OpenAICompatAdapter(ProviderAdapter):
    protocol = Protocol.OPENAI_COMPAT

    def __init__(self, api_key: str) -> None:
        # api_key 由 registry 从凭据存储解析后传入，绝不从环境变量兜底。
        self._api_key = api_key

    def supports(self, entry: ModelEntry) -> bool:
        return entry.protocol is Protocol.OPENAI_COMPAT

    def _client(self, entry: ModelEntry) -> AsyncOpenAI:
        return AsyncOpenAI(
            api_key=self._api_key,
            base_url=_normalize_base_url(entry.base_url),
            max_retries=0,  # 重试由 gateway.policy 统一控制，见 design.md 2.2 ④
        )

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        entry = req.model_entry
        # A-17：运行前按条目能力标记校验，不做「跑一半才崩」。
        if not entry.capabilities:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"模型条目 {entry.id} 未声明任何能力标记，拒绝调用",
            )
        client = self._client(entry)
        try:
            stream = await client.chat.completions.create(
                model=entry.model,
                messages=[{"role": m.role, "content": m.content} for m in req.messages],
                temperature=req.temperature,
                max_tokens=req.max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )
            async for event in stream:
                if event.choices and (delta := event.choices[0].delta) and delta.content:
                    yield ChatChunk(text=delta.content)
                if event.usage:
                    yield ChatChunk(
                        done=True,
                        usage=Usage(
                            input_tokens=event.usage.prompt_tokens,
                            output_tokens=event.usage.completion_tokens,
                            upstream_model=event.model,
                        ),
                    )
        except ApiError:
            raise
        except Exception as exc:  # 上游异常一律转成 model_unavailable
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"模型条目不二用：{entry.provider_label or entry.id} 调用失败",
                detail={"reason": type(exc).__name__},
            ) from exc

    async def probe_capabilities(self, entry: ModelEntry) -> set[Capability]:
        """探测结果只作建议值。中转站常谎报或漏报，所以管理员必须可覆盖（A-17）。"""
        caps = {Capability.STREAMING}
        try:
            client = self._client(entry)
            await client.models.list()
            caps.add(Capability.TOOL_CALLING)
        except Exception:
            pass
        return caps
