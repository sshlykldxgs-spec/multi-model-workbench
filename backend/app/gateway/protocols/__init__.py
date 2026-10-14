"""协议适配器。厂商 SDK 只允许出现在本目录（R-3，由 importlinter 强制）。

关键约束（design.md 12.8.4，已核实）：
  中转站与自建网关多数只提供 Chat Completions，不提供 Responses API。
  所以 openai_compat 默认用 chat.completions，不用 responses。

**惰性导入**：这里刻意不 eager import 三个适配器。
原因：适配器各自依赖厂商 SDK，若急切导入，则「只用 mock 或只用 OpenAI」的场景
也必须装齐 anthropic 与 google-genai —— 既拖慢启动，也让未配置的协议成为硬依赖。
改成按需解析后，只有 registry 真正要用某个协议时，才去 import 对应适配器。

（这是实测发现的问题：编写环境下 anthropic 缺失，导致 app.main 无法导入，
连 P0 的 mock 验收路径都跑不起来。）
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.gateway.protocols.anthropic import AnthropicAdapter
    from app.gateway.protocols.gemini import GeminiAdapter
    from app.gateway.protocols.openai_compat import OpenAICompatAdapter

__all__ = ["AnthropicAdapter", "GeminiAdapter", "OpenAICompatAdapter"]


def __getattr__(name: str) -> object:
    """PEP 562：属性被访问时才导入对应适配器。"""
    if name == "OpenAICompatAdapter":
        from app.gateway.protocols.openai_compat import OpenAICompatAdapter

        return OpenAICompatAdapter
    if name == "AnthropicAdapter":
        from app.gateway.protocols.anthropic import AnthropicAdapter

        return AnthropicAdapter
    if name == "GeminiAdapter":
        from app.gateway.protocols.gemini import GeminiAdapter

        return GeminiAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
