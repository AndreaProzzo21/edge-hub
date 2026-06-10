import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete, select

from app.core.config import settings
from app.models.heartbeat import Heartbeat
from app.infrastructure.database import async_session 

logger = logging.getLogger(__name__)

async def heartbeat_cleanup_task():
    """
    Background task that runs indefinitely every 24 hours.
    Removes old heartbeat records in small batches to prevent database locking.
    """
    BATCH_SIZE = 5000

    while True:
        try:
            retention_days = settings.HEARTBEAT_RETENTION_DAYS
            logger.info(f"Starting historical heartbeat cleanup (Retention: {retention_days} days)...")
            
            limit_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
            total_deleted = 0
            
            async with async_session() as db:
                while True:
                    # 1. Trova gli ID dei 5000 record più vecchi (Subquery)
                    subq = select(Heartbeat.id).where(Heartbeat.timestamp < limit_date).limit(BATCH_SIZE).subquery()
                    
                    # 2. Cancella solo quegli ID
                    stmt = delete(Heartbeat).where(Heartbeat.id.in_(select(subq)))
                    result = await db.execute(stmt)
                    await db.commit()
                    
                    deleted_in_batch = result.rowcount
                    total_deleted += deleted_in_batch
                    
                    # Se ha cancellato meno del batch, significa che abbiamo finito
                    if deleted_in_batch < BATCH_SIZE:
                        break
                    
                    # 3. FONDAMENTALE: Fai respirare il DB per far passare le altre query (es. nuovi heartbeat)
                    await asyncio.sleep(0.5)
                
            logger.info(f"Cleanup completed successfully. Removed a total of {total_deleted} records in batches.")
            
        except Exception as e:
            logger.error(f"Critical error during heartbeat cleanup: {e}")
        
        # Attende 24 ore prima del prossimo ciclo
        await asyncio.sleep(86400)