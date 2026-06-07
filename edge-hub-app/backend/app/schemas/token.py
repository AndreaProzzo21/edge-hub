from datetime import datetime
from pydantic import BaseModel, Field

class TokenCreate(BaseModel):
    label: str | None = Field(None, max_length=128)
    expires_in_hours: int = Field(24, ge=1, le=8760)

class TokenListItem(BaseModel):
    id: str
    label: str | None
    # Rimosso il campo 'used'
    expires_at: datetime
    is_valid: bool

    model_config = {"from_attributes": True}

class TokenResponse(BaseModel):
    id: str
    site_id: str
    raw_token: str
    expires_at: datetime
    label: str | None
    commands: dict[str, str]

    model_config = {"from_attributes": True}