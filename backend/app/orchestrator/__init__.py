"""编排层。唯一允许 import agent_framework 的包（R-1，由 importlinter 强制）。

业务代码只依赖本包暴露的自研接口（RoleExecutor、CheckpointStore 等）。
MAF 的实际接入在 P4，此处只放接口与骨架。
"""

from app.orchestrator.checkpoints.base import CheckpointStore
from app.orchestrator.executors.base import ReviewConclusion, RoleExecutor, RoleSlot

__all__ = ["CheckpointStore", "ReviewConclusion", "RoleExecutor", "RoleSlot"]
