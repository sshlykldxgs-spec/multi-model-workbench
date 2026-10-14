"""条目注册表：从数据库读取模型条目，构造适配器。

凭据解析规则（A-13）：
  团队密钥与个人密钥共存。凭据挂在条目上，条目可多个。
  个人条目（owner_id 非空）仅本人与管理员可见。
"""

from collections.abc import Iterable

from app.core.errors import ApiError, ErrorCode
from app.gateway.base import ModelEntry, Protocol, ProviderAdapter
from app.gateway.mock import MockAdapter


class AdapterRegistry:
    """按协议分发适配器。新增中转站通常只是加配置，不新增适配器。"""

    def __init__(self, credentials: dict[str, str]) -> None:
        #: credential_ref -> 密钥明文。密钥只从环境变量或密钥服务来，永不入库明文。
        self._credentials = credentials
        self._adapters: list[ProviderAdapter] = []

    def register(self, adapter: ProviderAdapter) -> None:
        self._adapters.append(adapter)

    @property
    def adapters(self) -> list[ProviderAdapter]:
        return list(self._adapters)

    def resolve(self, entry: ModelEntry) -> ProviderAdapter:
        if entry.id.startswith("mock"):
            return MockAdapter()
        for adapter in self._adapters:
            if adapter.protocol is entry.protocol and adapter.supports(entry):
                return adapter
        raise ApiError(
            ErrorCode.MODEL_UNAVAILABLE,
            f"没有可处理协议 {entry.protocol} 的适配器（条目 {entry.id}）",
        )

    def credential_for(self, entry: ModelEntry) -> str:
        key = self._credentials.get(entry.credential_ref)
        if not key:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"条目 {entry.id} 的凭据 {entry.credential_ref!r} 未配置",
            )
        return key


def _build_adapter(
    protocol: Protocol, credentials: dict[str, str], protocols: set[Protocol]
) -> ProviderAdapter:
    """按协议构造适配器。import 写在分支内，实现惰性加载。

    厂商 SDK 缺失时，只有真正用到该协议才报错，而不是一启动就崩。
    """
    if protocol is Protocol.OPENAI_COMPAT:
        from app.gateway.protocols.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter(_pick(credentials, protocols, Protocol.OPENAI_COMPAT))
    if protocol is Protocol.ANTHROPIC:
        from app.gateway.protocols.anthropic import AnthropicAdapter

        return AnthropicAdapter(_pick(credentials, protocols, Protocol.ANTHROPIC))
    if protocol is Protocol.GEMINI:
        from app.gateway.protocols.gemini import GeminiAdapter

        return GeminiAdapter(_pick(credentials, protocols, Protocol.GEMINI))
    raise ApiError(ErrorCode.MODEL_UNAVAILABLE, f"未知协议：{protocol}")


def build_default_registry(
    credentials: dict[str, str], entries: Iterable[ModelEntry]
) -> AdapterRegistry:
    """按已配置的条目构造注册表。

    只为实际用到的协议实例化适配器。这是刻意的：
    只用 mock 或只用 OpenAI 的场景，不该被迫装齐 anthropic 与 google-genai。
    """
    registry = AdapterRegistry(credentials)
    # 只处理**启用中**条目涉及的协议：停用的条目不该成为硬依赖，
    # 否则一个停用的 Gemini 条目会要求装 google-genai 才能启动。
    materialized = [e for e in entries if e.enabled]
    protocols = {e.protocol for e in materialized}
    for protocol in protocols:
        try:
            registry.register(_build_adapter(protocol, credentials, protocols))
        except ImportError as exc:
            raise ApiError(
                ErrorCode.MODEL_UNAVAILABLE,
                f"协议 {protocol} 的适配器依赖缺失：{exc.name}。"
                f"若不使用该协议，请把相关模型条目停用。",
            ) from exc
    return registry


def _pick(credentials: dict[str, str], protocols: set[Protocol], protocol: Protocol) -> str:
    """同一协议可能配多个条目、多个凭据。P0 取第一个可用的。

    P1 起改为按条目解析凭据（credential_for），这里只是骨架期的简化。
    """
    for value in credentials.values():
        if value:
            return value
    raise ApiError(ErrorCode.MODEL_UNAVAILABLE, f"协议 {protocol} 无可用凭据")
