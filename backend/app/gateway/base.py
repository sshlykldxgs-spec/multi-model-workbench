"""ModelGateway 与 ProviderAdapter 抽象。

R-3：任何模块不得直接 import 厂商 SDK；只能通过本层。
R-4：一切模型接入必须支持自定义 base_url（A-12）。
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Protocol(StrEnum):
    """协议类型。中转站绝大多数走 OPENAI_COMPAT（A-12）。"""

    OPENAI_COMPAT = "openai_compat"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class Capability(StrEnum):
    STREAMING = "streaming"
    TOOL_CALLING = "tool_calling"
    VISION = "vision"


@dataclass
class ModelEntry:
    """模型条目。凭据挂在条目上，团队密钥与个人密钥共存（A-13）。"""

    id: str
    protocol: Protocol
    model: str
    base_url: str | None = None
    provider_label: str = ""
    credential_ref: str = ""
    #: A-17：能力标记自动探测只作建议值，管理员可手动覆盖。
    #: 中转站实际能力常少于官方，甚至悄悄换模型。
    capabilities: set[Capability] = field(default_factory=set)
    #: 单价挂在条目上，不挂在模型名上 —— 中转站与官方价格不同。
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0
    is_relay: bool = False
    routing_priority: int = 100
    fallback_group: str | None = None
    #: A-13：个人私有条目仅本人与管理员可见。
    owner_id: str | None = None
    enabled: bool = True


@dataclass
class ChatMessage:
    role: str  # system | user | assistant | tool
    content: str
    tool_call_id: str | None = None
    name: str | None = None


@dataclass
class ChatChunk:
    """流式片段。"""

    text: str = ""
    #: 是否为本条消息的最后一片
    done: bool = False
    #: A-18：降级必须告知，不得静默换模型。
    fallback_from: str | None = None
    usage: "Usage | None" = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    #: 上游返回的真实模型名 —— 中转站可能返回与配置不同的 model 字段。
    upstream_model: str = ""


@dataclass
class ChatRequest:
    messages: list[ChatMessage]
    model_entry: ModelEntry
    temperature: float | None = None
    max_tokens: int | None = None
    tools: list[dict[str, Any]] | None = None
    idempotency_key: str | None = None


class ProviderAdapter(ABC):
    """按协议实现的适配器。

    新增一个中转站通常只是加一行配置，不需要新写适配器。
    """

    protocol: Protocol

    @abstractmethod
    def supports(self, entry: ModelEntry) -> bool: ...

    @abstractmethod
    def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...

    @abstractmethod
    async def probe_capabilities(self, entry: ModelEntry) -> set[Capability]:
        """自动探测能力。结果只作建议值，管理员可覆盖（A-17）。"""
        ...


class ModelGateway(ABC):
    """业务代码唯一依赖的模型接口（R-1）。"""

    @abstractmethod
    def stream_chat(self, req: ChatRequest) -> AsyncIterator[ChatChunk]: ...
