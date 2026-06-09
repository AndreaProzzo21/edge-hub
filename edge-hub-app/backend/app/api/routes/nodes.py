from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Aggiunto l'import per create_agent_jwt
from ...core.security import get_admin_session, create_agent_jwt
from ...infrastructure.database import get_db
from ...models.heartbeat import Heartbeat
from ...models.node import Node
from ...schemas.node import NodeResponse, NodePatch
from ...schemas.heartbeat import HeartbeatRecord

router = APIRouter(prefix="/nodes", tags=["nodes"])
AdminSessionDep = Depends(get_admin_session)


@router.get("/", response_model=list[NodeResponse], dependencies=[AdminSessionDep])
async def list_all_nodes(db: AsyncSession = Depends(get_db)):
    """Lista tutti i nodi di tutti i siti."""
    result = await db.execute(select(Node).order_by(Node.last_seen.desc().nullslast()))
    return result.scalars().all()


@router.get("/{node_id}", response_model=NodeResponse, dependencies=[AdminSessionDep])
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Recupera i dettagli di un singolo nodo tramite ID."""
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


@router.patch("/{node_id}", response_model=NodeResponse, dependencies=[AdminSessionDep])
async def patch_node(
    node_id: str,
    body: NodePatch,
    db: AsyncSession = Depends(get_db),
):
    """Aggiorna le informazioni modificabili di un nodo (es. descrizione)."""
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if body.description is not None:
        node.description = body.description
    await db.commit()
    await db.refresh(node)
    return node


# --- NUOVA ROUTE: COMMAND & CONTROL (Rinnovo JWT) ---
@router.post("/{node_id}/renew-jwt", dependencies=[AdminSessionDep], status_code=status.HTTP_200_OK)
async def renew_node_jwt(
    node_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Genera un nuovo JWT per il nodo e lo mette nella coda dei comandi.
    Implementa una protezione anti-spam (cooldown) tramite JTI: se c'è
    già un comando di rinnovo in attesa di essere prelevato dall'agente,
    rifiuta le richieste successive.
    """
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    # --- PROTEZIONE ANTI-SPAM (COOLDOWN) ---
    if node.pending_jti is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="A token renewal is already pending for this node. Please wait for the next heartbeat."
        )

    # Genera il nuovo token, ottieni JTI e ignora la scadenza qui (verrà salvata al ritiro)
    new_token, new_jti, _ = create_agent_jwt(node.id)

    # Autorizza il nuovo JTI impostandolo come pendente
    node.pending_jti = new_jti

    # Imbusta il comando nella colonna del database
    node.pending_command = {
        "action": "update_jwt",
        "payload": {
            "new_token": new_token
        }
    }
    
    await db.commit()
    
    return {"message": "Token renewal command queued successfully. The agent will pick it up at the next heartbeat."}


@router.delete("/{node_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminSessionDep])
async def remove_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Elimina il nodo e, tramite CASCADE, tutti i suoi heartbeat."""
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Nodo non trovato")
    
    await db.delete(node)
    await db.commit()
    return


@router.get("/{node_id}/heartbeats", response_model=list[HeartbeatRecord], dependencies=[AdminSessionDep])
async def get_node_heartbeats(
    node_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Restituisce gli ultimi N heartbeat di un nodo, dal più recente."""
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    result = await db.execute(
        select(Heartbeat)
        .where(Heartbeat.node_id == node_id)
        .order_by(Heartbeat.timestamp.desc())
        .limit(min(limit, 1000))
    )
    return result.scalars().all()