# app/schemas/token.py
from datetime import datetime
from pydantic import BaseModel, Field

class TokenCreate(BaseModel):
    label: str | None = Field(None, max_length=128)
    expires_in_hours: int = Field(24, ge=1, le=8760)

# Schema per la lista (più leggero)
class TokenListItem(BaseModel):
    id: str
    label: str | None
    used: bool
    expires_at: datetime
    is_valid: bool

    class Config:
        from_attributes = True  # <--- FONDAMENTALE

class TokenResponse(BaseModel):
    id: str
    site_id: str
    raw_token: str
    expires_at: datetime
    label: str | None
    commands: dict[str, str]

    class Config:
        from_attributes = True # <--- FONDAMENTALE