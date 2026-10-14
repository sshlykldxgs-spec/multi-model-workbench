"""认证与授权。

蓝图第 8 节：管理员邀请制，密码用 argon2，会话 Cookie 设 HttpOnly 与 SameSite。
角色只有 admin 与 member。
"""

from typing import Annotated

from fastapi import Depends, Request
from itsdangerous import BadSignature, TimestampSigner

from app.core.config import Settings, get_settings
from app.core.errors import ApiError, ErrorCode
from app.schemas.auth import CurrentUser
from app.models.enums import UserRole


def _signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.session_secret, salt="session")


def issue_session(user_id: str, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    return _signer(settings).sign(user_id.encode()).decode()


def read_session(token: str, settings: Settings | None = None) -> str | None:
    settings = settings or get_settings()
    try:
        return _signer(settings).unsign(token, max_age=settings.session_max_age_seconds).decode()
    except BadSignature:
        return None


async def get_current_user(request: Request) -> CurrentUser:
    """从 Cookie 解析当前用户。

    P0 骨架：只验签名并构造用户；真实用户查询在 P1 接入数据库后补。
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ApiError(ErrorCode.UNAUTHORIZED, "未登录或会话已过期")
    user_id = read_session(token, settings)
    if not user_id:
        raise ApiError(ErrorCode.UNAUTHORIZED, "未登录或会话已过期")
    return CurrentUser(id=user_id, email="", role=UserRole.MEMBER)


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.role is not UserRole.ADMIN:
        raise ApiError(ErrorCode.FORBIDDEN, "需要管理员权限")
    return user
