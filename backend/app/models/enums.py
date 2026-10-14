from enum import StrEnum


class UserRole(StrEnum):
    ADMIN = "admin"
    MEMBER = "member"


class RunStatus(StrEnum):
    """design.md 第 8 节：六种状态，前端都要有对应视觉。"""

    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class DocumentStatus(StrEnum):
    QUEUED = "queued"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class ToolRisk(StrEnum):
    """蓝图 5.4：风险分级。后两者默认需要人工确认。"""

    READ_ONLY = "read_only"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class Visibility(StrEnum):
    """A-19 / 蓝图第 13 节第 3 项：会话默认私有，知识库可团队共享。"""

    PRIVATE = "private"
    TEAM = "team"


class ConfigVersionStatus(StrEnum):
    DRAFT = "draft"
    PUBLISHED = "published"
