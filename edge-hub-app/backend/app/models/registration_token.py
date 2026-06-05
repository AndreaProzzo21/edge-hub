from datetime import datetime, timezone, timedelta
from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

DEFAULT_EXPIRY_HOURS = 24

class RegistrationToken(Base):
    __tablename__ = "registration_tokens"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    
    # Collegamento al sito con eliminazione a cascata
    site_id: Mapped[str] = mapped_column(
        ForeignKey("sites.id", ondelete="CASCADE"), 
        index=True
    )
    

    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Relazioni ORM
    site: Mapped["Site"] = relationship(back_populates="tokens")
    node: Mapped["Node | None"] = relationship(
        "Node", 
        back_populates="token",
        uselist=False
    )

    def release(self):
        """Libera il token rendendolo di nuovo utilizzabile."""
        self.used = False
        self.node_id = None

    @classmethod
    def make_expiry(cls, hours: int = DEFAULT_EXPIRY_HOURS) -> datetime:
        return datetime.now(timezone.utc) + timedelta(hours=hours)

    @property
    def is_valid(self) -> bool:
        return not self.used and datetime.now(timezone.utc) < self.expires_at