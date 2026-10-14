"""数据模型。对应蓝图第 6 节 + design.md 第 10 节的补充字段。

命名与契约一致（snake_case、UUID 主键）。
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TenantMixin, TimestampMixin, new_uuid


class User(Base, TimestampMixin, TenantMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(16), default="member")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    #: 为封控预留（A-14）。第一版不写逻辑。
    is_suspended: Mapped[bool] = mapped_column(Boolean, default=False)
    suspended_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ModelEntryRow(Base, TimestampMixin, TenantMixin):
    """模型注册表。design.md 第 10 节：补充中转站与路由字段。

    单价挂在条目上而不是模型名上 —— 中转站与官方价格不同（A-12 ⑤）。
    """

    __tablename__ = "models"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    #: openai_compat | anthropic | gemini
    protocol: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    #: 官方端点、Azure 端点或中转站地址。必须以 /v1 结尾（design.md 12.8.4）。
    base_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    provider_label: Mapped[str] = mapped_column(String(128), default="")
    #: 凭据的引用名，不是密钥本身。密钥只从环境变量或密钥服务读。
    credential_ref: Mapped[str] = mapped_column(String(128), default="")
    #: A-17：能力标记自动探测只作建议值，此字段是管理员的手动覆盖。
    capabilities: Mapped[list[str]] = mapped_column(JSONB, default=list)
    input_price_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    output_price_per_mtok: Mapped[float] = mapped_column(Float, default=0.0)
    #: 是否经中转。界面要能区分，并提示数据经第三方转发。
    is_relay: Mapped[bool] = mapped_column(Boolean, default=False)
    routing_priority: Mapped[int] = mapped_column(Integer, default=100)
    fallback_group: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: A-13：个人私有条目仅本人与管理员可见。
    owner_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class Conversation(Base, TimestampMixin, TenantMixin):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200), default="新会话")
    default_model_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    #: 会话默认私有（蓝图第 13 节第 3 项）。
    visibility: Mapped[str] = mapped_column(String(16), default="private")


class Message(Base, TimestampMixin, TenantMixin):
    """消息表是历史的唯一事实来源（ADR-0002）。

    每次运行时把中性格式历史重建为 MAF 上下文；不依赖框架的序列化。
    """

    __tablename__ = "messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(16))
    #: 分段内容：文本、工具调用、引用。见契约的 message 结构。
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    model_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class Run(Base, TimestampMixin, TenantMixin):
    __tablename__ = "runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    conversation_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(24), default="queued", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    spent_usd: Mapped[float] = mapped_column(Float, default=0.0)
    #: 记录所用配置版本，历史运行可复现（design.md 7.4）。
    config_version_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    #: 配置区试运行标记。
    is_test: Mapped[bool] = mapped_column(Boolean, default=False)
    #: 幂等键：POST /runs 需带，防止重复扣费。
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)


class RunEvent(Base, TenantMixin):
    """运行事件流水，可回放。

    design.md 第 8 节：前端按序号断线续传，所以 (run_id, seq) 必须唯一。
    """

    __tablename__ = "run_events"
    __table_args__ = (UniqueConstraint("run_id", "seq", name="uq_run_events_run_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("runs.id", ondelete="CASCADE"), index=True
    )
    seq: Mapped[int] = mapped_column(Integer)
    event: Mapped[str] = mapped_column(String(48))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now()
    )


class UsageLog(Base, TenantMixin):
    """用量与成本。

    design.md 第 10 节：补充 unit_price_snapshot / cost_center / upstream_model / is_fallback。
    单价快照防止改价影响历史账目。
    """

    __tablename__ = "usage_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    model_id: Mapped[str] = mapped_column(String(36))
    #: 上游返回的真实模型名 —— 中转站可能返回与配置不同的 model 字段。
    upstream_model: Mapped[str] = mapped_column(String(128), default="")
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    unit_price_in_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    unit_price_out_snapshot: Mapped[float] = mapped_column(Float, default=0.0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    #: A-18：降级必须可追溯。
    is_fallback: Mapped[bool] = mapped_column(Boolean, default=False)
    #: A-19：个人自备额度与团队配额分开显示。
    cost_center: Mapped[str] = mapped_column(String(16), default="team")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now()
    )


class AuditLog(Base, TenantMixin):
    """审计。蓝图第 8 节：登录、工具审批、文件上传与删除、配置变更全部写入。"""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(128), nullable=True)
    #: 载荷必须脱敏（core.logging.sanitize）。
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    result: Mapped[str] = mapped_column(String(16), default="ok")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now()
    )


class Skill(Base, TimestampMixin, TenantMixin):
    """技能表（A-26 配套）。

    格式沿用 MAF 的 SKILL.md 约定：name（≤64，小写字母数字连字符）与
    description（单行 ≤1024），正文为 Markdown。不自定义字段。

    P0 只建表不加逻辑，避免 P5 改迁移。
    """

    __tablename__ = "skills"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(64), index=True)
    description: Mapped[str] = mapped_column(String(1024), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    #: 附带资源（脚本、模板、参考文档）的清单。
    resources: Mapped[list[dict]] = mapped_column(JSONB, default=list)
    owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    visibility: Mapped[str] = mapped_column(String(16), default="private")
    #: 管理员发布的官方技能可默认关闭「加载/读取」审批；脚本执行一律保留审批。
    is_official: Mapped[bool] = mapped_column(Boolean, default=False)


class PolicyEvent(Base, TenantMixin):
    """内容策略命中记录。A-14：为监管与内容审核预留，P0 只建表。"""

    __tablename__ = "policy_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_uuid)
    run_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    direction: Mapped[str] = mapped_column(String(16), default="inbound")
    policy: Mapped[str] = mapped_column(String(48), default="")
    action: Mapped[str] = mapped_column(String(24), default="allow")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=__import__("sqlalchemy").func.now()
    )
