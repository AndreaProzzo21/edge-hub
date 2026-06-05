from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class HeartbeatRequest(BaseModel):
    # Metriche base — obbligatorie
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    uptime_seconds: float = Field(..., ge=0)

    # Campi semi-strutturati — opzionali, indicizzati sul DB per query rapide
    container_count: int | None = None
    pod_count: int | None = None
    ip_address: str | None = None

    # Tutto il resto — ogni agente ci mette quello che vuole
    extra_data: dict[str, Any] | None = None


class HeartbeatResponse(BaseModel):
    status: str = "ok"
    node_id: str
    timestamp: datetime


class HeartbeatRecord(BaseModel):
    """Usato nelle route GET /nodes/{id}/heartbeats."""
    id: int
    node_id: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime_seconds: float
    container_count: int | None
    pod_count: int | None
    ip_address: str | None
    extra_data: dict[str, Any] | None
    timestamp: datetime

    model_config = {"from_attributes": True}