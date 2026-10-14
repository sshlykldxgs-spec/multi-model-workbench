def test_list_models_returns_mock(admin_client) -> None:
    """P0 验收：能看到可用模型及能力标记。"""
    resp = admin_client.get("/api/v1/models")
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert any(m["id"] == "mock-echo" for m in items)


def test_relay_entry_flagged(admin_client) -> None:
    """中转条目必须带 is_relay，界面要据此提示数据经第三方转发。"""
    resp = admin_client.get("/api/v1/models")
    # 默认条目里中转条目是停用的，所以列表里看不到；直接验证模型层数据。
    from app.api.v1.models import default_entries

    relay = next(e for e in default_entries() if e.is_relay)
    assert relay.base_url and relay.base_url.endswith("/v1")
