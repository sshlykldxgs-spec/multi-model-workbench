"""结构化日志。

蓝图第 8 节与第 9 节要求：日志带 run_id 与 user_id，且必须脱敏。
见 backend/AGENTS.md 第 10 节的禁止事项。
"""

import json
import logging
import re
from typing import Any

#: 一律脱敏的键名片段（大小写不敏感）。
SENSITIVE_KEY_PARTS = (
    "key",
    "token",
    "secret",
    "password",
    "authorization",
    "cookie",
    "credential",
    "api_key",
)

#: 形如 sk-xxx / Bearer xxx 的值也脱敏。
_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{8,}", re.IGNORECASE),
)

MASK = "***REDACTED***"


def _is_sensitive(key: str) -> bool:
    low = key.lower()
    return any(part in low for part in SENSITIVE_KEY_PARTS)


def _mask_value(value: Any) -> Any:
    if isinstance(value, str):
        out = value
        for pattern in _VALUE_PATTERNS:
            out = pattern.sub(MASK, out)
        return out
    return value


def sanitize(obj: Any) -> Any:
    """递归脱敏。用于日志与审计载荷。"""
    if isinstance(obj, dict):
        return {
            k: (MASK if _is_sensitive(str(k)) else sanitize(_mask_value(v))) for k, v in obj.items()
        }
    if isinstance(obj, (list, tuple)):
        return [sanitize(v) for v in obj]
    return _mask_value(obj)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # 结构化字段由 logger.info(..., extra={"run_id": ...}) 传入
        for field in ("request_id", "run_id", "user_id", "conversation_id", "model_id"):
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(sanitize(payload), ensure_ascii=False)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """取一个模块级 logger。

    存在的意义是让各模块统一走这里，而不是各自 `logging.getLogger(__name__)` ——
    这样将来要换 handler、加过滤器或改级别，只改一处。
    configure_logging() 负责配置根 logger，本函数只负责取名。
    """
    return logging.getLogger(name)
