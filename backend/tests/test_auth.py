def test_login_sets_httponly_cookie(client) -> None:
    """蓝图第 8 节：会话 Cookie 必须 HttpOnly + SameSite。"""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "admin12345"},
    )
    assert resp.status_code == 200
    set_cookie = resp.headers["set-cookie"].lower()
    assert "httponly" in set_cookie, "会话 Cookie 必须设 HttpOnly"
    assert "samesite" in set_cookie, "会话 Cookie 必须设 SameSite"


def test_me_requires_login(client) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthorized"
    assert body["error"]["request_id"]


def test_me_after_login(admin_client) -> None:
    resp = admin_client.get("/api/v1/auth/me")
    assert resp.status_code == 200
    assert resp.json()["role"] == "admin"


def test_wrong_password_does_not_reveal_account_existence(client) -> None:
    """不区分「邮箱不存在」与「密码错误」，避免账号枚举。"""
    r1 = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "x1234567"}
    )
    r2 = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "wrongwrong"}
    )
    assert r1.status_code == r2.status_code == 401
    assert r1.json()["error"]["message"] == r2.json()["error"]["message"]


def test_login_rate_limited(client) -> None:
    """蓝图第 8 节要求登录限流。"""
    codes = [
        client.post(
            "/api/v1/auth/login", json={"email": "a@b.com", "password": "x1234567"}
        ).status_code
        for _ in range(15)
    ]
    assert 429 in codes, f"连续失败登录应触发限流，实际状态码：{codes}"
