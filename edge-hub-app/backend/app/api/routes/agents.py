import hashlib
import uuid
import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import create_agent_jwt, decode_agent_jwt
from ...infrastructure.database import get_db
from ...models.heartbeat import Heartbeat
from ...models.node import Node, NodeStatus
from ...models.registration_token import RegistrationToken
from ...models.site import Site
from ...schemas.agent import AgentRegisterRequest, AgentRegisterResponse
from ...schemas.heartbeat import HeartbeatRequest, HeartbeatResponse
from ...services.alert_engine import dispatch_recovery_alerts
from .websockets import ws_manager

router = APIRouter(prefix="/agents", tags=["agents"])
bearer = HTTPBearer()

# ---------------------------------------------------------------------------
# Dependency: La "Ghigliottina". Se il nodo è stato cancellato dal DB, 
# restituisce 401 e l'agente remoto si autodistrugge in modo pulito.
# ---------------------------------------------------------------------------
async def get_current_node(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Node:
    try:
        node_id = decode_agent_jwt(credentials.credentials)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired agent token",
        )

    node = await db.get(Node, node_id)
    if not node:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Node not found or revoked by administrator",
        )
    return node


# ---------------------------------------------------------------------------
# POST /agents/register
# ---------------------------------------------------------------------------
@router.post("/register", response_model=AgentRegisterResponse, status_code=status.HTTP_201_CREATED)
async def register_agent(
    body: AgentRegisterRequest,
    db: AsyncSession = Depends(get_db),
):
    # 1. Cerca e valida il token
    token_hash = hashlib.sha256(body.registration_token.encode()).hexdigest()
    result = await db.execute(
        select(RegistrationToken).where(RegistrationToken.token_hash == token_hash)
    )
    db_token = result.scalar_one_or_none()

    if not db_token or not db_token.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid, expired, or already used registration token",
        )

    # 2. Crea il nodo (senza più token_id)
    node = Node(
        id=str(uuid.uuid4()),
        site_id=db_token.site_id,
        hostname=body.hostname,
        description=body.description,
        agent_type=body.agent_type,
        agent_version=body.agent_version,
        os=body.os,
        arch=body.arch,
        status=NodeStatus.ONLINE,
        last_seen=datetime.now(timezone.utc),
    )
    db.add(node)

    # 3. IL TOKEN KAMIKAZE: Il token ha fatto il suo lavoro, lo distruggiamo per sempre.
    await db.delete(db_token)

    await db.commit()
    await db.refresh(node)

    # 4. Emetti il JWT dell'agente a lunghissima scadenza (es. 10 anni)
    agent_token = create_agent_jwt(node.id)

    asyncio.create_task(ws_manager.broadcast(node.site_id, {
        "event_type": "node_registered",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node_id": node.id,
        "hostname": node.hostname,
        "message": f"New agent registered: {node.hostname}"
    }))

    return AgentRegisterResponse(node_id=node.id, agent_token=agent_token)


# ---------------------------------------------------------------------------
# POST /agents/heartbeat
# ---------------------------------------------------------------------------
@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    body: HeartbeatRequest,
    node: Node = Depends(get_current_node),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    hb = Heartbeat(
        node_id=node.id,
        cpu_usage=body.cpu_usage,
        memory_usage=body.memory_usage,
        disk_usage=body.disk_usage,
        uptime_seconds=body.uptime_seconds,
        ip_address=body.ip_address,
        extra_data=body.extra_data,
        timestamp=now,
    )
    db.add(hb)

    node.last_seen = now
    node.status = NodeStatus.ONLINE
    node.cpu_usage = body.cpu_usage      
    node.mem_usage = body.memory_usage
    node.uptime_seconds = body.uptime_seconds

    # --- LOGICA ALERT ENGINE ---
    if getattr(node, 'offline_cycles', 0) > 0 or getattr(node, 'offline_alert_sent', False):
        if getattr(node, 'offline_alert_sent', False):
            site = await db.get(Site, node.site_id)
            if site:
                asyncio.create_task(dispatch_recovery_alerts(node, site))
        
        node.offline_cycles = 0
        node.offline_alert_sent = False

    await db.commit()

    asyncio.create_task(ws_manager.broadcast(node.site_id, {
        "event_type": "heartbeat",
        "timestamp": now.isoformat(),
        "node_id": node.id,
        "hostname": node.hostname,
        "telemetry": {
            "cpu_usage": body.cpu_usage,
            "memory_usage": body.memory_usage,
            "disk_usage": body.disk_usage
        }
    }))
    
    return HeartbeatResponse(node_id=node.id, timestamp=now)


@router.get("/me")
async def get_me(node: Node = Depends(get_current_node)):
    return {
        "node_id": node.id,
        "hostname": node.hostname,
        "site_id": node.site_id,
        "status": node.status,
        "last_seen": node.last_seen,
    }