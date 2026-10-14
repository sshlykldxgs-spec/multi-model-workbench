def test_health_ok(client) -> None:
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_request_id_header_present(client) -> None:
    """每个响应都要带 X-Request-ID，前端与审计都依赖它。"""
    resp = client.get("/api/v1/health")
    assert resp.headers.get("X-Request-ID")
