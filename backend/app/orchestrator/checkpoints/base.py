"""检查点存储（design.md 12.2，已核实）。

核实结论：MAF **无官方 Postgres 实现**，P4 必须自研。接口形状已明确 ——
内置的 InMemory / File / Cosmos 实现都满足同一个协议，Cosmos 实现给出 6 个方法。

自研 Postgres 实现要满足的两条硬要求（design.md 12.2.1）：
  1. 实现下面 6 个方法；事务性与并发写语义官方未定义，必须自己定清楚并写测试。
  2. 状态用 JSON 优先；必须 pickle 的类型要显式注册
     （allowed_checkpoint_types 或 agent_framework.register_checkpoint_type），
     并确保反序列化只来自我们自己的库表 —— 官方明确把检查点存储当作信任边界。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class Checkpoint:
    checkpoint_id: str
    workflow_name: str
    created_at: str
    state: dict[str, Any]


class CheckpointStore(ABC):
    """6 个方法，对齐 MAF 的 CheckpointStorage 协议。"""

    @abstractmethod
    async def save(self, workflow_name: str, checkpoint_id: str, state: dict[str, Any]) -> None: ...

    @abstractmethod
    async def load(self, workflow_name: str, checkpoint_id: str) -> Checkpoint | None: ...

    @abstractmethod
    async def get_latest(self, workflow_name: str) -> Checkpoint | None: ...

    @abstractmethod
    async def list_checkpoints(self, workflow_name: str) -> list[Checkpoint]: ...

    @abstractmethod
    async def list_checkpoint_ids(self, workflow_name: str) -> list[str]: ...

    @abstractmethod
    async def delete(self, workflow_name: str, checkpoint_id: str) -> None: ...
