"""Anthropic 原生协议适配器。"""

from collections.abc import AsyncIterator
from typing import Any

from anthropic import AsyncAnthropic

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


class AnthropicAdapter(ProviderAdapter):
    protocol = Protocol.ANTHROPIC

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def supports(self, entry: ModelEntry) -> bool:
        return entry.protocol is Protocol.ANTHROPIC

    def _client(self, entry: ModelEntry) -> AsyncAnthropic:
        kwargs: dict[str, object] = {"api_key": self._api_key, "max_retries": 0}
        if entry.base_url:
            kwargs["base_url"] = entry.base_url.rstrip("/")
        return AsyncAnthropic(**kwargs)  # type: ignore[arg-type]

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        entry = req.model_entry
        # Anthropic 要求 system 单独传，且首个消息必须是 user。
        system = "\n".join(m.content for m in req.messages if m.role == "system")
        turns = [
            {"role": m.role, "content": m.content}
            for m in req.messages
            if m.role in {"user", "assistant"}
        ]
        client = self._client(entry)
        try:
            # 注意：anthropic 1.13.0 的 messages.stream 已不接受 temperature 参数
            # （pyright 实测报 No parameter named "temperature"）。
            # 需要采样温度时走 extra_body，不要直接加参数。
            extra: dict[str, Any] = {}
            if req.temperature is not None:
                extra["temperature"] = req.temperature
            # system 为空时**必须不传这个参数**：SDK 的类型是
            # str | Iterable[TextBlockParam] | Omit，显式传 None 不合法。
            stream_kwargs: dict[str, Any] = {
                "model": entry.model,
                "messages": turns,
                "max_tokens": req.max_tokens or 4096,
            }
            if system:
                stream_kwargs["system"] = system
            if extra:
                stream_kwargs["extra_body"] = extra
            async with client.messages.stream(**stream_kwargs) as stream:
                async for text in stream.text_stream:
                    yield ChatChunk(text=text)
                final = await stream.get_final_message()
                yield ChatChunk(
                    done=True,
                    usage=Usage(
                        input_tokens=final.usage.input_tokens,
                        output_tokens=final.usage.output_tokens,
                        upstream_model=final.model,
                    ),
                )
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"Anthropic 条目调用失败：{entry.provider_label or entry.id}",
                detail={"reason": type(exc).__name__},
            ) from exc

    async def probe_capabilities(self, entry: ModelEntry) -> set[Capability]:
        return {Capability.STREAMING, Capability.TOOL_CALLING}
