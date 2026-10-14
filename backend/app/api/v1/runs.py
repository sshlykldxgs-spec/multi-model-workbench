"""运行与 SSE 事件流。

这是 P0 验收的核心：选 mock 模型发一句话，看到逐字输出。

契约要点（docs/api-contract.md 第 6、12 节）：
  - POST /conversations/{id}/runs 启动运行，以 SSE 返回事件
  - GET  /runs/{id}/events?after=序号 断线续传
  - 每个事件带递增序号
"""

import asyncio
import time
from collections.abc import AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import StreamingResponse

from app.core.deps import get_budget_policy
from app.core.errors import ApiError, ErrorCode
from app.gateway.base import ChatMessage, ChatRequest, ModelEntry
from app.gateway.service import GatewayService
from app.middleware.auth import get_current_user
from app.middleware.policies.base import BudgetPolicy, PolicyContext
from app.models.enums import RunStatus
from app.schemas.chat import RunCreate, RunOut
from app.schemas.events import EventName, EventEnvelope

router = APIRouter()

#: P0 骨架的运行态存储，P1 换成 runs / run_events 表。
_RUNS: dict[str, dict[str, Any]] = {}
_EVENTS: dict[str, list[EventEnvelope]] = {}
_CANCELLED: set[str] = set()


def _sse(event: EventEnvelope) -> str:
    """SSE 帧。id 用序号，前端据此续传（契约第 12 节）。"""
    return (
        f"event: {event.event}\n"
        f"id: {event.seq}\n"
        f"data: {event.model_dump_json()}\n\n"
    )


def _next_seq(run_id: str) -> int:
    return len(_EVENTS.get(run_id, [])) + 1


def _emit(run_id: str, event: str, payload: dict[str, Any]) -> EventEnvelope:
    env = EventEnvelope(
        run_id=run_id,
        seq=_next_seq(run_id),
        ts=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        event=event,
        payload=payload,
    )
    _EVENTS.setdefault(run_id, []).append(env)
    return env


def _pick_entry(request: Request, model_id: str) -> ModelEntry:
    entries: list[ModelEntry] = request.app.state.model_entries
    entry = next((e for e in entries if e.id == model_id), None)
    if entry is None:
        raise ApiError(ErrorCode.NOT_FOUND, f"模型条目 {model_id} 不存在")
    if not entry.enabled:
        raise ApiError(
            ErrorCode.MODEL_UNAVAILABLE,
            f"模型条目 {entry.provider_label or entry.id} 当前已停用",
        )
    return entry


@router.post("/conversations/{conversation_id}/runs")
async def start_run(
    conversation_id: str,
    body: RunCreate,
    request: Request,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    budget: Annotated[BudgetPolicy, Depends(get_budget_policy)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> StreamingResponse:
    entry = _pick_entry(request, body.model_id)

    # 预算检查（蓝图第 9 节：超限自动中止）。具体数值未定，见 decisions.md D-2。
    decision = await budget.check(
        PolicyContext(
            user_id=user.id,
            conversation_id=conversation_id,
            run_id=None,
            model_entry_id=entry.id,
            estimated_cost_usd=None,
        )
    )
    if not decision.allowed:
        raise ApiError(ErrorCode.BUDGET_EXCEEDED, "已超出预算上限，运行被拒绝")

    gateway: GatewayService = request.app.state.gateway
    run_id = f"run-{int(time.time() * 1000)}"
    _RUNS[run_id] = {
        "id": run_id,
        "conversation_id": conversation_id,
        "status": RunStatus.RUNNING,
        "spent_usd": 0.0,
        "model_id": entry.id,
        "user_id": user.id,
    }

    async def pipeline() -> AsyncIterator[str]:
        started = _emit(run_id, EventName.RUN_STARTED, {"run_id": run_id, "template": "chat"})
        yield _sse(started)
        message_id = f"msg-{run_id}"
        try:
            req = ChatRequest(
                messages=[ChatMessage(role="user", content=body.input)],
                model_entry=entry,
                idempotency_key=idempotency_key,
            )
            async for chunk in gateway.stream_chat(req):
                if run_id in _CANCELLED:
                    yield _sse(
                        _emit(run_id, EventName.RUN_FAILED, {"status": str(RunStatus.CANCELLED)})
                    )
                    _RUNS[run_id]["status"] = RunStatus.CANCELLED
                    return
                if chunk.fallback_from:
                    # A-18：降级必须告知，不得静默换模型。
                    yield _sse(
                        _emit(
                            run_id,
                            EventName.MESSAGE_DELTA,
                            {
                                "message_id": message_id,
                                "text": f"（上游 {chunk.fallback_from} 不可用，已降级到 {entry.provider_label or entry.id}）\n",
                            },
                        )
                    )
                if chunk.text:
                    yield _sse(
                        _emit(
                            run_id,
                            EventName.MESSAGE_DELTA,
                            {"message_id": message_id, "text": chunk.text},
                        )
                    )
                if chunk.usage:
                    cost = gateway.cost_usd(entry, chunk.usage)
                    _RUNS[run_id]["spent_usd"] = cost
                    yield _sse(
                        _emit(
                            run_id,
                            EventName.USAGE,
                            {
                                "input_tokens": chunk.usage.input_tokens,
                                "output_tokens": chunk.usage.output_tokens,
                                "upstream_model": chunk.usage.upstream_model,
                                "cost_usd": round(cost, 6),
                            },
                        )
                    )
                await asyncio.sleep(0)

            yield _sse(_emit(run_id, EventName.MESSAGE_COMPLETED, {"message_id": message_id}))
            _RUNS[run_id]["status"] = RunStatus.SUCCEEDED
            yield _sse(
                _emit(
                    run_id,
                    EventName.RUN_COMPLETED,
                    {
                        "status": str(RunStatus.SUCCEEDED),
                        "spent_usd": round(_RUNS[run_id]["spent_usd"], 6),
                    },
                )
            )
        except ApiError as exc:
            _RUNS[run_id]["status"] = RunStatus.FAILED
            _RUNS[run_id]["error_code"] = str(exc.code)
            yield _sse(
                _emit(
                    run_id,
                    EventName.RUN_FAILED,
                    {"status": str(RunStatus.FAILED), "error_code": str(exc.code), "message": exc.message},
                )
            )

    return StreamingResponse(
        pipeline(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # 关掉 Caddy/nginx 的缓冲，否则流式会被攒起来
            "Connection": "keep-alive",
        },
    )


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> RunOut:
    run = _RUNS.get(run_id)
    if run is None:
        raise ApiError(ErrorCode.NOT_FOUND, "运行不存在")
    return RunOut(
        id=run["id"],
        conversation_id=run["conversation_id"],
        status=str(run["status"]),
        spent_usd=run["spent_usd"],
        error_code=run.get("error_code"),
    )


@router.get("/runs/{run_id}/events")
async def get_events(
    run_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    after: int = 0,
) -> list[EventEnvelope]:
    """断线续传：返回序号大于 after 的事件（契约第 6 节）。"""
    if run_id not in _RUNS:
        raise ApiError(ErrorCode.NOT_FOUND, "运行不存在")
    return [e for e in _EVENTS.get(run_id, []) if e.seq > after]


@router.post("/runs/{run_id}/cancel")
async def cancel_run(
    run_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    run = _RUNS.get(run_id)
    if run is None:
        raise ApiError(ErrorCode.NOT_FOUND, "运行不存在")
    if run["status"] in {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED}:
        # 对已终结的运行发取消 → 409，契约里 run_conflict 就是为此存在。
        raise ApiError(ErrorCode.RUN_CONFLICT, "运行已结束，无法取消")
    _CANCELLED.add(run_id)
    return {"ok": True}


@router.post("/runs/{run_id}/approvals/{request_id}")
async def decide_approval(
    run_id: str,
    request_id: str,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    approve: bool = True,
) -> dict[str, Any]:
    """人工确认。P2 接工具审批后填实。

    注意（design.md 12.3，官方已知限制）：框架的审批响应目前只带布尔值，
    不能附带意见或修改后的参数。所以 approvals 表要自己存这些（蓝图已如此设计）。
    """
    if run_id not in _RUNS:
        raise ApiError(ErrorCode.NOT_FOUND, "运行不存在")
    return {"ok": True, "request_id": request_id, "approved": approve}
