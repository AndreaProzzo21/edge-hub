from pydantic import BaseModel, Field
from datetime import datetime


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

class AgentRegisterRequest(BaseModel):
    registration_token: str = Field(..., min_length=1)
    hostname: str = Field(..., min_length=1, max_length=256)
    description: str | None = Field(None, max_length=512)
    agent_type: str = Field(..., pattern="^(linux|docker|kubernetes)$")
    agent_version: str = Field(..., max_length=64)
    os: str | None = Field(None, max_length=128)
    arch: str | None = Field(None, max_length=32)


class AgentRegisterResponse(BaseModel):
    node_id: str
    agent_token: str   # JWT da usare per tutti i successivi heartbeat

