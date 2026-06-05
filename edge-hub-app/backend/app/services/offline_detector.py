"""
Task asincrono che gira in background e marca offline
i nodi che non mandano heartbeat da NODE_OFFLINE_THRESHOLD_SECONDS.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select, update

from ..core.config import settings
from ..infrastructure.database import async_session
from ..models.node import Node, NodeStatus

logger = logging.getLogger(__name__)


async def _check_once() -> None:
    threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.NODE_OFFLINE_THRESHOLD_SECONDS
    )
    async with async_session() as db:
        # Aggiorna in batch tutti i nodi online che non si vedono da troppo
        result = await db.execute(
            select(Node).where(
                Node.status == NodeStatus.ONLINE,
                Node.last_seen < threshold,
            )
        )
        stale_nodes = result.scalars().all()

        if stale_nodes:
            ids = [n.id for n in stale_nodes]
            await db.execute(
                update(Node)
                .where(Node.id.in_(ids))
                .values(status=NodeStatus.OFFLINE)
            )
            await db.commit()
            logger.info(
                "Marked %d node(s) as offline: %s",
                len(ids),
                ", ".join(ids),
            )


async def offline_detector_loop() -> None:
    """Loop infinito — da lanciare come asyncio task nel lifespan."""
    logger.info(
        "Offline detector started (threshold=%ds, interval=%ds)",
        settings.NODE_OFFLINE_THRESHOLD_SECONDS,
        settings.OFFLINE_CHECK_INTERVAL_SECONDS,
    )
    while True:
        try:
            await _check_once()
        except Exception:
            logger.exception("Error in offline detector")
        await asyncio.sleep(settings.OFFLINE_CHECK_INTERVAL_SECONDS)