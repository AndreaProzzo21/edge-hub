import secrets
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

def generate_jwt_secret() -> str:
    """Genera un segreto casuale e sicuro a 32 byte (circa 43 caratteri in base64)."""
    return secrets.token_urlsafe(32)

class Settings(BaseSettings):
    DATABASE_URL: str

    # Nessun default: se manca nel file .env, l'app/container NON parte.
    ADMIN_API_KEY: str

    # Origins CORS consentiti separati da virgola. Default "*" per retrocompatibilità.
    CORS_ORIGINS: str = "*"

    # Se omesso nell'env, chiama la funzione generate_jwt_secret all'avvio
    JWT_SECRET_KEY: str = Field(default_factory=generate_jwt_secret)
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 5256000

    # Dopo quanti secondi un nodo passa a "offline"
    NODE_OFFLINE_THRESHOLD_SECONDS: int = 100

    # Intervallo del task che controlla i nodi offline (secondi)
    OFFLINE_CHECK_INTERVAL_SECONDS: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()