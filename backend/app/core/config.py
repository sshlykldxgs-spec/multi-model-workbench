"""集中配置。一切来自环境变量，密钥不进仓库、不进数据库明文。"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "多模型工作台"
    env: str = "development"
    debug: bool = False

    # --- 数据库 ---
    database_url: str = "postgresql+asyncpg://workbench:workbench@localhost:5432/workbench"

    # --- 会话 Cookie ---
    # 蓝图第 8 节：Cookie 必须 HttpOnly + SameSite。
    session_cookie_name: str = "wb_session"
    session_secret: str = Field(default="dev-only-change-me", min_length=8)
    session_max_age_seconds: int = 60 * 60 * 12
    cookie_secure: bool = False  # 生产（HTTPS）必须置 true

    # --- 登录限流（蓝图第 8 节要求）---
    login_rate_limit_per_minute: int = 10

    # --- 预算（A-19 起：团队配额与个人自备额度分开）---
    # 具体数值未定（decisions.md D-2），这里只放开关与告警阈值。
    budget_warn_ratio: float = 0.8
    budget_hard_ratio: float = 1.0

    # --- 可观测 ---
    otel_exporter_otlp_endpoint: str = ""
    # 蓝图第 8 节要求日志脱敏，所以默认关闭敏感数据采集。
    # 见 design.md 12.8.1：开启会把 prompt、system 指令、工具参数写进 span。
    otel_enable_sensitive_data: bool = False

    # --- 中转站（A-12）---
    # 默认 false：所有条目参数显式传入，不依赖环境变量推断（design.md 12.8.4）。
    allow_env_model_inference: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
