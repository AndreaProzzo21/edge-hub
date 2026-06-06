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
    
    async with async_session() as db:
        # Seleziona i nodi che non comunicano da troppo tempo
        # e per cui NON abbiamo ancora inviato l'alert finale.
        # Usa selectinload per recuperare in modo efficiente i dati del Sito (webhook).
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
        alert_count = 0

        for node in stale_nodes:
            # Cambia lo stato in OFFLINE se era ONLINE
            if node.status == NodeStatus.ONLINE:
                node.status = NodeStatus.OFFLINE
            
            # Incrementa il contatore dei cicli offline
            node.offline_cycles += 1
            updated_count += 1

            # Controllo soglia dei 3 cicli
            if node.offline_cycles >= 3:
                # Evita di spammare nei cicli futuri
                node.offline_alert_sent = True
                alert_count += 1
                
                # Lancia l'invio dei webhook in background senza bloccare il database
                if node.site:
                    asyncio.create_task(dispatch_offline_alerts(node, node.site))

        # Eseguiamo il commit solo se c'è stato almeno un aggiornamento
        if updated_count > 0:
            await db.commit()
            logger.info(
                "Processati %d nodi stale (aggiornamento cicli e status). Inviati %d alert.",
                updated_count,
                alert_count
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