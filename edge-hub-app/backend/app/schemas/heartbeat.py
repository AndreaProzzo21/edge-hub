from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# --- NUOVI SCHEMAS PER IL COMMAND & CONTROL ---
class AgentCommand(BaseModel):
    action: str = Field(..., description="Il tipo di azione, ad esempio 'update_jwt'")
    payload: dict[str, Any] = Field(..., description="I dati necessari all'azione, ad esempio {'new_token': '...'}")


class HeartbeatRequest(BaseModel):
    # Metriche base — obbligatorie
    cpu_usage: float = Field(..., ge=0, le=100)
    memory_usage: float = Field(..., ge=0, le=100)
    disk_usage: float = Field(..., ge=0, le=100)
    uptime_seconds: float = Field(..., ge=0)
    ip_address: str | None = None

    # Tutto il resto — ogni agente ci mette quello che vuole
    extra_data: dict[str, Any] | None = None


class HeartbeatResponse(BaseModel):
    status: str = "ok"
    node_id: str
    timestamp: datetime
    # Aggiungiamo il campo command. Se è None, l'agente Go sa che non c'è nulla da fare.
    command: AgentCommand | None = None 


class HeartbeatRecord(BaseModel):
    """Usato nelle route GET /nodes/{id}/heartbeats."""
    id: int
    node_id: str
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    uptime_seconds: float
    ip_address: str | None
    extra_data: dict[str, Any] | None
    timestamp: datetime

    model_config = {"from_attributes": True}