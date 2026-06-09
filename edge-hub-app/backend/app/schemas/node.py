from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class NodeResponse(BaseModel):
    id: str
    site_id: str
    hostname: str
    description: str | None
    agent_type: str
    agent_version: str
    os: str | None
    arch: str | None
    cpu_usage: float | None
    mem_usage: float | None
    uptime_seconds: float | None
    status: str
    last_seen: datetime | None
    created_at: datetime
    
    # --- CAMPI ALERT ENGINE ---
    offline_cycles: int
    offline_alert_sent: bool

    # --- CAMPI COMMAND & CONTROL & SICUREZZA ---
    # Mostra se c'è un comando in attesa di essere ritirato dall'agente
    pending_command: dict[str, Any] | None = None
    
    # Mostra la data di scadenza reale del JWT attualmente attivo
    jwt_expires_at: datetime | None = None

    model_config = {"from_attributes": True}

class NodePatch(BaseModel):
    description: str | None = Field(None, max_length=512)