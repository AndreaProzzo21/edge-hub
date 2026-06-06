from datetime import datetime
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
    
    # --- NUOVI CAMPI ALERT ENGINE ---
    offline_cycles: int
    offline_alert_sent: bool

    model_config = {"from_attributes": True}

class NodePatch(BaseModel):
    description: str | None = Field(None, max_length=512)
