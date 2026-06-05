from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..core.config import settings
from ..models.base import Base  # noqa: F401
from ..models import site, node, registration_token, heartbeat  # noqa: F401 — registra i model con Base

engine = create_async_engine(settings.DATABASE_URL, echo=False)

async_session = async_sessionmaker(
    engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session


async def create_tables() -> None:
    """Crea tutte le tabelle (usato all'avvio in sviluppo)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)