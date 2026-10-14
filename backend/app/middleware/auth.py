"""认证与授权。

蓝图第 8 节：管理员邀请制，密码用 argon2，会话 Cookie 设 HttpOnly 与 SameSite。
角色只有 admin 与 member。
"""

from typing import Annotated

from fastapi import Depends, Request
from itsdangerous import BadSignature, TimestampSigner

from app.core.config import Settings, get_settings
from app.core.errors import ApiError, ErrorCode
from app.models.enums import UserRole
from app.schemas.auth import CurrentUser


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

    P0 骨架：验签后到 app.state 的引导用户目录里取真实身份。
    这里**必须**查目录而不是硬编码角色 —— 实测过：硬编码 MEMBER 会让
    管理员登录后被识别成成员，test_me_after_login 因此失败。
    P1 接入 users 表后，把 _lookup_bootstrap_user 换成数据库查询。
    """
    settings = get_settings()
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise ApiError(ErrorCode.UNAUTHORIZED, "未登录或会话已过期")
    user_id = read_session(token, settings)
    if not user_id:
        raise ApiError(ErrorCode.UNAUTHORIZED, "未登录或会话已过期")

    user = _lookup_bootstrap_user(request, user_id)
    if user is None:
        # 会话签名有效但用户已不存在（例如被禁用或删除）
        raise ApiError(ErrorCode.UNAUTHORIZED, "账号不可用，请重新登录")
    return user


def _lookup_bootstrap_user(request: Request, user_id: str) -> CurrentUser | None:
    """P0 的用户目录：只有一个引导管理员，存在 app.state 上。

    P1 起替换为 users 表查询（含 is_active / is_suspended 判断）。
    """
    directory: dict[str, CurrentUser] = getattr(request.app.state, "bootstrap_users", {})
    return directory.get(user_id)


async def require_admin(
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> CurrentUser:
    if user.role is not UserRole.ADMIN:
        raise ApiError(ErrorCode.FORBIDDEN, "需要管理员权限")
    return user
