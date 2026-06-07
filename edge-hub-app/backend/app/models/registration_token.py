from datetime import datetime, timezone, timedelta
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

DEFAULT_EXPIRY_HOURS = 24

class RegistrationToken(Base):
    __tablename__ = "registration_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), 
        index=True
    )

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relazioni ORM (Solo verso il Site, non più verso il Node)
    site: Mapped["Site"] = relationship(back_populates="tokens")

    @classmethod
    def make_expiry(cls, hours: int = DEFAULT_EXPIRY_HOURS) -> datetime:
        return datetime.now(timezone.utc) + timedelta(hours=hours)

    @property
    def is_valid(self) -> bool:
        # È valido solo se non è scaduto (se esiste nel DB, diamo per scontato che non sia usato)
        return datetime.now(timezone.utc) < self.expires_at