"""协议适配器。厂商 SDK 只允许出现在本目录（R-3，由 importlinter 强制）。

关键约束（design.md 12.8.4，已核实）：
  中转站与自建网关多数只提供 Chat Completions，不提供 Responses API。
  所以 openai_compat 默认用 chat.completions，不用 responses。
"""

from app.gateway.protocols.anthropic import AnthropicAdapter
from app.gateway.protocols.gemini import GeminiAdapter
from app.gateway.protocols.openai_compat import OpenAICompatAdapter

__all__ = ["AnthropicAdapter", "GeminiAdapter", "OpenAICompatAdapter"]
