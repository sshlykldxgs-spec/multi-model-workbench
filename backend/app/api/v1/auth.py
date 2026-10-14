"""认证。蓝图第 8 节：管理员邀请制、argon2、HttpOnly + SameSite、登录限流。"""

from typing import Annotated

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError
from fastapi import APIRouter, Depends, Request, Response

from app.core.config import get_settings
from app.core.deps import get_rate_limit_policy
from app.core.errors import ApiError, ErrorCode
from app.middleware.auth import get_current_user, issue_session
from app.middleware.policies.base import RateLimitPolicy
from app.schemas.auth import CurrentUser, LoginRequest, MeResponse

router = APIRouter()

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


@router.post("/login")
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    rate_limit: Annotated[RateLimitPolicy, Depends(get_rate_limit_policy)],
) -> MeResponse:
    settings = get_settings()

    # 登录限流（蓝图第 8 节）。P0 用进程内实现，多 worker 需换共享存储。
    client_ip = request.client.host if request.client else "unknown"
    decision = await rate_limit.check(
        f"login:{client_ip}", settings.login_rate_limit_per_minute
    )
    if not decision.allowed:
        raise ApiError(ErrorCode.RATE_LIMITED, "登录尝试过于频繁，请稍后再试")

    # P0 骨架：无数据库时用环境变量里的管理员账号验证。
    # P1 接入 users 表后改查库。
    admin_email = request.app.state.bootstrap_admin_email
    admin_hash = request.app.state.bootstrap_admin_hash
    if body.email != admin_email or not verify_password(admin_hash, body.password):
        # 不区分「邮箱不存在」与「密码错误」，避免账号枚举。
        raise ApiError(ErrorCode.UNAUTHORIZED, "邮箱或密码不正确")

    user_id = "bootstrap-admin"
    token = issue_session(user_id, settings)
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_max_age_seconds,
        httponly=True,          # 蓝图第 8 节硬要求
        samesite="lax",         # 蓝图第 8 节硬要求
        secure=settings.cookie_secure,
        path="/",
    )
    return MeResponse(id=user_id, email=admin_email, role=request.app.state.bootstrap_admin_role)


@router.post("/logout")
async def logout(response: Response) -> dict[str, bool]:
    response.delete_cookie(get_settings().session_cookie_name, path="/")
    return {"ok": True}


@router.get("/me")
async def me(user: Annotated[CurrentUser, Depends(get_current_user)]) -> MeResponse:
    return MeResponse(id=user.id, email=user.email, role=user.role)
