from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importiamo la dipendenza per la sessione web (cookie)
from ...core.security import get_admin_session
from ...infrastructure.database import get_db
from ...models.heartbeat import Heartbeat
from ...models.node import Node
from ...schemas.node import NodeResponse, NodePatch
from ...schemas.heartbeat import HeartbeatRecord
from app.services.node_manager import delete_node_and_recycle_token

router = APIRouter(prefix="/nodes", tags=["nodes"])

# Questa dipendenza proteggerà le rotte tramite Cookie HttpOnly
AdminSessionDep = Depends(get_admin_session)


@router.get("/", response_model=list[NodeResponse], dependencies=[AdminSessionDep])
async def list_all_nodes(db: AsyncSession = Depends(get_db)):
    """Lista tutti i nodi di tutti i siti."""
    result = await db.execute(select(Node).order_by(Node.last_seen.desc().nullslast()))
    return result.scalars().all()


@router.get("/{node_id}", response_model=NodeResponse, dependencies=[AdminSessionDep])
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
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
    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    if body.description is not None:
        node.description = body.description
    await db.commit()
    await db.refresh(node)
    return node


@router.delete("/{node_id}")
async def remove_node(node_id: str, db: AsyncSession = Depends(get_db)):
    try:
        await delete_node_and_recycle_token(db, node_id)
        return {"message": "Nodo eliminato e token riciclato con successo"}
    except ValueError:
        raise HTTPException(status_code=404, detail="Nodo non trovato")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{node_id}/heartbeats", response_model=list[HeartbeatRecord], dependencies=[AdminSessionDep])
async def get_node_heartbeats(
    node_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Ultimi N heartbeat di un nodo, dal più recente."""
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