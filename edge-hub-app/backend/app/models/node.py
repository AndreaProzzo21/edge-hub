from datetime import datetime
from enum import Enum
from sqlalchemy import DateTime, ForeignKey, String, Float, Column, Integer, Boolean, JSON
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
    
    hostname: Mapped[str] = mapped_column(String(256))
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    agent_type: Mapped[str] = mapped_column(String(32))
    agent_version: Mapped[str] = mapped_column(String(64))
    os: Mapped[str | None] = mapped_column(String(128), nullable=True)
    arch: Mapped[str | None] = mapped_column(String(32), nullable=True)

    status: Mapped[str] = mapped_column(String(16), default=NodeStatus.UNKNOWN)
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cpu_usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    mem_usage: Mapped[float | None] = mapped_column(Float, nullable=True)
    uptime_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    offline_cycles = Column(Integer, default=0, nullable=False)
    offline_alert_sent = Column(Boolean, default=False, nullable=False)
    last_alert_timestamps: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    # --- COMMAND & CONTROL & SICUREZZA ---
    pending_command: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    active_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    pending_jti: Mapped[str | None] = mapped_column(String(36), nullable=True)
    jwt_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relazioni
    site: Mapped["Site"] = relationship(back_populates="nodes")
    heartbeats: Mapped[list["Heartbeat"]] = relationship(
        back_populates="node", 
        cascade="all, delete-orphan"
    )