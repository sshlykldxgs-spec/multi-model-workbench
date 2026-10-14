"""可观测性配置。

**为什么这个函数在编排层**：蓝图与 design.md 的 R-1 规定
「MAF 只允许出现在 app/orchestrator/ 内」。
而开启追踪要调用 MAF 的 `configure_otel_providers`，
所以这段代码必须待在这一层，由 main.py 以普通函数调用，
而不是让 main.py 自己去 import agent_framework。

如果放在 main.py，分层门禁（app/scripts/check_layering.py）会直接判违规 ——
这正是实测发生过的。
"""

from __future__ import annotations

import os

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def configure_observability(settings: Settings) -> bool:
    """开启 OTel 追踪。返回是否真的开启。

    三个已核实的坑（design.md 12.8.1）：

    1. **OTLP 协议必须显式设置**。不设时框架默认 gRPC，
       未装 gRPC exporter 会抛 ImportError。我们用 http/protobuf。
    2. **provider 只在创建时读一次环境变量**，
       所以调用方必须先 `load_dotenv()` 再调本函数。
    3. **`enable_sensitive_data` 会把 prompt、system 指令、工具参数写进 span**，
       与蓝图第 8 节「日志必须脱敏」冲突，生产环境必须保持关闭。
    """
    if not settings.otel_exporter_otlp_endpoint:
        return False

    os.environ.setdefault("OTEL_EXPORTER_OTLP_PROTOCOL", "http/protobuf")
    os.environ.setdefault("OTEL_SERVICE_NAME", "workbench-backend")
    if settings.otel_enable_sensitive_data:
        os.environ.setdefault("ENABLE_SENSITIVE_DATA", "true")

    try:
        from agent_framework.observability import configure_otel_providers
    except ImportError as exc:  # 未装 MAF 或该模块不存在时不该让服务起不来
        logger.warning("OTel 未开启，MAF observability 不可用：%s", exc)
        return False

    configure_otel_providers(enable_sensitive_data=settings.otel_enable_sensitive_data)
    logger.info("OTel 追踪已开启（sensitive_data=%s）", settings.otel_enable_sensitive_data)
    return True
