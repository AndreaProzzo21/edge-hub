from datetime import datetime, timezone

from sqlalchemy import DateTime
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Base class per tutti i modelli SQLAlchemy."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_now,
    )