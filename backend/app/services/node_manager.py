# app/services/node_manager.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy import select
from app.models.node import Node

async def delete_node_and_recycle_token(db: AsyncSession, node_id: str):
    """
    Elimina il nodo e, se presente, resetta il suo token di registrazione
    per renderlo nuovamente disponibile.
    """
    # 1. Recupera il nodo includendo la relazione 'token' 
    # (selectinload carica il token collegato in una sola query)
    result = await db.execute(
        select(Node).options(selectinload(Node.token)).where(Node.id == node_id)
    )
    node = result.scalar_one_or_none()
    
    if not node:
        raise ValueError("Nodo non trovato")

    # 2. Se c'è un token associato, usiamo il metodo release() creato nel modello
    if node.token:
        node.token.release()
    
    # 3. Elimina il nodo dal database
    await db.delete(node)
    
    # 4. Conferma l'operazione
    await db.commit()