"""Anthropic 原生协议适配器。"""

from collections.abc import AsyncIterator

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
            async with client.messages.stream(
                model=entry.model,
                system=system or None,
                messages=turns,  # type: ignore[arg-type]
                max_tokens=req.max_tokens or 4096,
                temperature=req.temperature,
            ) as stream:
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
