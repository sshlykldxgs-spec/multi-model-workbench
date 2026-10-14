from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    title: str = "新会话"
    default_model_id: str | None = None


class ConversationOut(BaseModel):
    id: str
    title: str
    default_model_id: str | None
    visibility: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: dict
    model_id: str | None
    run_id: str | None


class RunCreate(BaseModel):
    """启动一次运行。

    契约要求带 Idempotency-Key 头防止重复扣费。
    """

    model_id: str
    input: str = Field(min_length=1, description="用户本轮的输入")


class RunOut(BaseModel):
    id: str
    conversation_id: str | None
    status: str
    spent_usd: float
    error_code: str | None = None
