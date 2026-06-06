from datetime import datetime
from pydantic import BaseModel, Field

class SiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    
    # --- NUOVI CAMPI WEBHOOK ---
    discord_webhook_url: str | None = Field(None, description="URL del Webhook di Discord")
    slack_webhook_url: str | None = Field(None, description="URL del Webhook di Slack")


class SitePatch(BaseModel):
    """Schema per permettere all'utente di aggiornare un sito esistente"""
    name: str | None = Field(None, min_length=1, max_length=128)
    description: str | None = Field(None, max_length=512)
    discord_webhook_url: str | None = Field(None)
    slack_webhook_url: str | None = Field(None)


class SiteResponse(BaseModel):
    id: str
    name: str
    description: str | None
    created_at: datetime
    
    # --- NUOVI CAMPI ESPOSTI AL FRONTEND ---
    discord_webhook_url: str | None
    slack_webhook_url: str | None

    model_config = {"from_attributes": True}