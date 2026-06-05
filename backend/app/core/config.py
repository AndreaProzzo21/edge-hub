from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str

    # Chiave admin per proteggere le route operative
    ADMIN_API_KEY: str = "change-me-in-production"

    # JWT per i token degli agenti (dopo la registrazione)
    JWT_SECRET_KEY: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24 * 365  # 1 anno: gli agenti non si riautenticano

    # Dopo quanti secondi un nodo passa a "offline"
    NODE_OFFLINE_THRESHOLD_SECONDS: int = 90

    # Intervallo del task che controlla i nodi offline (secondi)
    OFFLINE_CHECK_INTERVAL_SECONDS: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()