"""SSE 事件。

契约第 12 节：每个事件带递增序号，前端据此断线重连。
统一信封：run_id、seq、ts、event、payload。
"""

from typing import Any

from pydantic import BaseModel

from app.models.enums import RunStatus


class EventEnvelope(BaseModel):
    run_id: str
    seq: int
    ts: str
    event: str
    payload: dict[str, Any]


#: 契约第 12 节的事件名。封闭集合，新增必须改契约。
class EventName:
    RUN_STARTED = "run.started"
    PLAN_CREATED = "plan.created"
    STEP_STARTED = "step.started"
    STEP_COMPLETED = "step.completed"
    MESSAGE_DELTA = "message.delta"
    MESSAGE_COMPLETED = "message.completed"
    TOOL_CALL_STARTED = "tool.call.started"
    TOOL_CALL_COMPLETED = "tool.call.completed"
    APPROVAL_REQUESTED = "approval.requested"
    REVIEW_RESULT = "review.result"
    CITATIONS = "citations"
    USAGE = "usage"
    RUN_FAILED = "run.failed"
    RUN_COMPLETED = "run.completed"


TERMINAL_STATUSES = frozenset(
    {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}
)
