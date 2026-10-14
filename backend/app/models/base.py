"""ORM 基类。

A-16：关键表加可空 tenant_id，只加列不加逻辑。
单租户时恒为 NULL；将来做多租户时不必改所有查询。
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class TenantMixin:
    """A-16：预留多租户。只加列，不加任何过滤逻辑。"""

    tenant_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)


def new_uuid() -> str:
    return str(uuid.uuid4())
