import asyncio
import logging
from datetime import datetime, timedelta, timezone
from sqlalchemy import delete

from app.core.config import settings
from app.models.heartbeat import Heartbeat
from app.infrastructure.database import async_session 

logger = logging.getLogger(__name__)

async def heartbeat_cleanup_task():
    """
    Background task that runs indefinitely every 24 hours.
    Removes heartbeat records older than the days specified in the environment variables.
    """
    while True:
        try:
            # Reads the updated value directly from the system settings
            retention_days = settings.HEARTBEAT_RETENTION_DAYS
            logger.info(f"Starting historical heartbeat cleanup (Retention: {retention_days} days)...")
            
            async with async_session() as db:
                limit = datetime.now(timezone.utc) - timedelta(days=retention_days)
                
                # Definition and execution of the deletion query
                stmt = delete(Heartbeat).where(Heartbeat.timestamp < limit)
                result = await db.execute(stmt)
                await db.commit()
                
                logger.info(f"Cleanup completed successfully. Removed {result.rowcount} records.")
        except Exception as e:
            logger.error(f"Critical error during heartbeat cleanup: {e}")
        
        # Suspends execution for 24 hours (86400 seconds) before the next cycle.
        # Since this is a massive delete on time-series data, running it once a day
        # is the ideal approach to avoid stressing the database.
        await asyncio.sleep(86400)