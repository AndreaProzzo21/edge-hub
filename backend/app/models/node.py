from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

class NodeStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    UNKNOWN = "unknown"

class AgentType(str, Enum):
    LINUX = "linux"
    DOCKER = "docker"
    KUBERNETES = "kubernetes"

class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    site_id: Mapped[str] = mapped_column(ForeignKey("sites.id", ondelete="CASCADE"), index=True)
    
    # Riferimento al token che ha creato questo nodo
    token_id: Mapped[str | None] = mapped_column(
        ForeignKey("registration_tokens.id", ondelete="SET NULL"),
        nullable=True,
        unique=True
    )

    hostname: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(32))
    agent_version: Mapped[str] = mapped_column(String(64))
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    arch: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=NodeStatus.UNKNOWN)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relazioni
    site: Mapped["Site"] = relationship(back_populates="nodes")

    token: Mapped["RegistrationToken | None"] = relationship(
        "RegistrationToken", 
        back_populates="node",
        foreign_keys=[token_id]
    )
    heartbeats: Mapped[list["Heartbeat"]] = relationship(
        back_populates="node", 
        cascade="all, delete-orphan"
    )