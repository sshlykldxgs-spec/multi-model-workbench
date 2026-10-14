from pydantic import BaseModel, Field


class ModelInfo(BaseModel):
    """GET /models 的条目。

    is_relay 必须返回：界面要标注「此模型经中转提供服务，能力可能与官方不同」
    并提示数据经第三方转发（design.md 2.2 ③⑦）。
    """

    id: str
    protocol: str
    model: str
    provider_label: str
    capabilities: list[str]
    is_relay: bool = False
    enabled: bool = True


class ModelCreate(BaseModel):
    protocol: str = Field(description="openai_compat | anthropic | gemini")
    model: str
    base_url: str | None = None
    provider_label: str = ""
    credential_ref: str = ""
    capabilities: list[str] = Field(default_factory=list)
    input_price_per_mtok: float = 0.0
    output_price_per_mtok: float = 0.0
    is_relay: bool = False
    routing_priority: int = 100
    fallback_group: str | None = None


class ModelTestResult(BaseModel):
    ok: bool
    detail: str = ""
    detected_capabilities: list[str] = Field(default_factory=list)
