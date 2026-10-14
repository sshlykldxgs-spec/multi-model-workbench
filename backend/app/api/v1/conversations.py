"""会话与消息。

行为准则：会话默认私有；查询一律按运行者过滤（不做多租户，但可见性要真做）。
"""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.middleware.auth import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.chat import ConversationCreate, ConversationOut
from app.schemas.common import Page

router = APIRouter()


@router.get("/conversations")
async def list_conversations(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> Page[ConversationOut]:
    """P0 骨架：内存态。

    P1 起查 conversations 表，并强制 user_id 过滤 —— 见下方 assert。
    """
    return Page[ConversationOut](items=[])


@router.post("/conversations")
async def create_conversation(
    body: ConversationCreate,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ConversationOut:
    from app.core.errors import ApiError, ErrorCode

    raise ApiError(ErrorCode.NOT_FOUND, "会话持久化在 P1 交付")
