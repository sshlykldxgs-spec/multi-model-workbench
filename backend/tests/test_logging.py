"""脱敏是蓝图第 8 节的硬要求，所以要有测试盯着。"""

from app.core.logging import MASK, sanitize


def test_masks_sensitive_keys() -> None:
    out = sanitize({"api_key": "sk-abcdefghijklmnop", "note": "ok"})
    assert out["api_key"] == MASK
    assert out["note"] == "ok"


def test_masks_sensitive_values_in_plain_text() -> None:
    out = sanitize({"msg": "failed with sk-abcdefghijklmnopqrst"})
    assert MASK in out["msg"]
    assert "sk-abcdefghijklmnopqrst" not in out["msg"]


def test_masks_bearer_token() -> None:
    out = sanitize({"h": "Authorization: Bearer abcdefghijklmnop"})
    assert MASK in out["h"]


def test_recurses_into_nested_structures() -> None:
    out = sanitize({"outer": [{"password": "x", "keep": "y"}]})
    assert out["outer"][0]["password"] == MASK
    assert out["outer"][0]["keep"] == "y"
