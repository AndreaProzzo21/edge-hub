import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete
from app.models.heartbeat import Heartbeat
# Importa il sessionmaker che hai definito nel tuo database.py
from app.infrastructure.database import async_session 

logger = logging.getLogger(__name__)

async def heartbeat_cleanup_task(retention_days: int = 7):
    while True:
        try:
            logger.info("Avvio pulizia heartbeat storici...")
            # Crea la sessione manualmente
            async with async_session() as db:
                limit = datetime.now(timezone.utc) - timedelta(days=retention_days)
                stmt = delete(Heartbeat).where(Heartbeat.timestamp < limit)
                result = await db.execute(stmt)
                await db.commit()
                logger.info(f"Pulizia completata. Rimossi {result.rowcount} record.")
        except Exception as e:
            logger.error(f"Errore durante la pulizia degli heartbeat: {e}")
        
        # Aspetta 24 ore
        await asyncio.sleep(86400)