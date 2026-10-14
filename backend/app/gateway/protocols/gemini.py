"""Google Gemini 原生协议适配器。"""

from collections.abc import AsyncIterator

from google import genai

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


class GeminiAdapter(ProviderAdapter):
    protocol = Protocol.GEMINI

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    def supports(self, entry: ModelEntry) -> bool:
        return entry.protocol is Protocol.GEMINI

    def _client(self, entry: ModelEntry) -> "genai.Client":
        return genai.Client(api_key=self._api_key)

    async def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]:
        entry = req.model_entry
        client = self._client(entry)
        prompt = "\n".join(f"{m.role}: {m.content}" for m in req.messages)
        try:
            stream = await client.aio.models.generate_content_stream(
                model=entry.model,
                contents=prompt,
            )
            async for chunk in stream:
                if chunk.text:
                    yield ChatChunk(text=chunk.text)
                if (meta := getattr(chunk, "usage_metadata", None)) is not None:
                    yield ChatChunk(
                        done=True,
                        usage=Usage(
                            input_tokens=getattr(meta, "prompt_token_count", 0) or 0,
                            output_tokens=getattr(meta, "candidates_token_count", 0) or 0,
                            upstream_model=entry.model,
                        ),
                    )
        except ApiError:
            raise
        except Exception as exc:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"Gemini 条目调用失败：{entry.provider_label or entry.id}",
                detail={"reason": type(exc).__name__},
            ) from exc

    async def probe_capabilities(self, entry: ModelEntry) -> set[Capability]:
        return {Capability.STREAMING, Capability.TOOL_CALLING, Capability.VISION}
