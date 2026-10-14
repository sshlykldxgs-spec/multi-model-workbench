import json


def _sse_events(text: str) -> list[dict]:
    events = []
    for block in text.strip().split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_run_streams_mock_output(admin_client) -> None:
    """P0 核心验收：选 mock 模型发一句话，看到逐字输出。"""
    resp = admin_client.post(
        "/api/v1/conversations/c1/runs",
        json={"model_id": "mock-echo", "input": "你好"},
        headers={"Idempotency-Key": "test-key-1"},
    )
    assert resp.status_code == 200
    events = _sse_events(resp.text)
    names = [e["event"] for e in events]

    assert "run.started" in names
    assert names[-1] == "run.completed"
    assert "usage" in names

    deltas = [e for e in events if e["event"] == "message.delta"]
    assert len(deltas) > 3, "mock 必须逐字流式吐字，不能一次返回整段"
    assert "你好" in "".join(d["payload"]["text"] for d in deltas)


def test_event_seq_is_monotonic(admin_client) -> None:
    """契约：每个事件带递增序号，前端据此断线重连。"""
    resp = admin_client.post(
        "/api/v1/conversations/c1/runs",
        json={"model_id": "mock-echo", "input": "测试序号"},
        headers={"Idempotency-Key": "test-key-2"},
    )
    seqs = [e["seq"] for e in _sse_events(resp.text)]
    assert seqs == sorted(seqs)
    assert len(set(seqs)) == len(seqs), "序号不能重复"


def test_unknown_model_returns_not_found(admin_client) -> None:
    resp = admin_client.post(
        "/api/v1/conversations/c1/runs",
        json={"model_id": "does-not-exist", "input": "hi"},
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "not_found"


def test_disabled_model_rejected(admin_client) -> None:
    """停用条目必须拒绝，且错误码是 model_unavailable。"""
    resp = admin_client.post(
        "/api/v1/conversations/c1/runs",
        json={"model_id": "relay-example", "input": "hi"},
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "model_unavailable"


def test_run_requires_login(client) -> None:
    resp = client.post(
        "/api/v1/conversations/c1/runs",
        json={"model_id": "mock-echo", "input": "hi"},
    )
    assert resp.status_code == 401
