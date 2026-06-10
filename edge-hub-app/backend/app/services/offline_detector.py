"""
Task asincrono che gira in background e marca offline
i nodi che non mandano heartbeat da NODE_OFFLINE_THRESHOLD_SECONDS.
Gestisce anche l'invio degli alert (webhook) al raggiungimento dei 3 cicli.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from ..core.config import settings
from ..infrastructure.database import async_session
from ..models.node import Node, NodeStatus
from ..services.alert_engine import dispatch_offline_alerts

logger = logging.getLogger(__name__)


async def _check_once() -> None:
    threshold = datetime.now(timezone.utc) - timedelta(
        seconds=settings.NODE_OFFLINE_THRESHOLD_SECONDS
    )
    
    # 1. Creiamo una coda temporanea per gli alert
    alerts_to_dispatch = []
    
    async with async_session() as db:
        result = await db.execute(
            select(Node)
            .options(selectinload(Node.site))
            .where(
                Node.last_seen < threshold,
                Node.offline_alert_sent == False
            )
        )
        stale_nodes = result.scalars().all()

        updated_count = 0

        for node in stale_nodes:
            if node.status == NodeStatus.ONLINE:
                node.status = NodeStatus.OFFLINE
            
            node.offline_cycles += 1
            updated_count += 1

            if node.offline_cycles >= 3:
                node.offline_alert_sent = True
                
                # 2. Invece di sparare il task subito, lo mettiamo in coda
                if node.site:
                    alerts_to_dispatch.append((node, node.site))

        if updated_count > 0:
            await db.commit()
            logger.info(
                "Processed %d stale nodes. Queued %d alerts for dispatch.",
                updated_count,
                len(alerts_to_dispatch)
            )

    # 3. Fuori dalla sessione DB, avviamo un singolo task per smaltire la coda
    if alerts_to_dispatch:
        asyncio.create_task(_process_alerts_with_delay(alerts_to_dispatch))


async def _process_alerts_with_delay(alerts: list) -> None:
    """
    Processa la coda degli alert inserendo un ritardo artificiale (Rate Limiting)
    per evitare di essere bannati dalle API di Discord/Slack (Errore 429).
    """
    for node, site in alerts:
        try:
            await dispatch_offline_alerts(node, site)
        except Exception as e:
            logger.error(f"Errore durante l'invio dell'alert per il nodo {node.id}: {e}")
        
        # Pausa di mezzo secondo tra un webhook e l'altro (Max 2 messaggi al secondo)
        await asyncio.sleep(0.5)


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