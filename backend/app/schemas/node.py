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
    status: str
    last_seen: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class NodePatch(BaseModel):
    description: str | None = Field(None, max_length=512)