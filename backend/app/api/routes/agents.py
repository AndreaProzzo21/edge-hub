import hashlib
import uuid
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
from ...schemas.agent import (
    AgentRegisterRequest,
    AgentRegisterResponse
)
from ...schemas.heartbeat import (
    HeartbeatRequest,
    HeartbeatResponse
)

router = APIRouter(prefix="/agents", tags=["agents"])
bearer = HTTPBearer()


# ---------------------------------------------------------------------------
# Dependency: estrae e valida il JWT dell'agente
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
            detail="Node not found",
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
    # 1. Cerca il token (codice esistente)
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

    # 2. Crea il nodo
    # Nota: Assicurati che il modello Node abbia un campo 'token_id' 
    # che punta alla ForeignKey del token
    node = Node(
        id=str(uuid.uuid4()),
        token_id=db_token.id, # <--- COLLEGAMENTO BIDIREZIONALE
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

    # 3. Marca il token come usato e aggancia il node_id
    db_token.used = True
    db_token.node_id = node.id # <--- AGGANCIO AL TOKEN

    await db.commit()
    await db.refresh(node)

    # 4. Emetti il JWT dell'agente
    agent_token = create_agent_jwt(node.id)

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
        container_count=body.container_count,
        pod_count=body.pod_count,
        ip_address=body.ip_address,
        extra_data=body.extra_data,
        timestamp=now,
    )
    db.add(hb)

    node.last_seen = now
    node.status = NodeStatus.ONLINE

    await db.commit()

    return HeartbeatResponse(node_id=node.id, timestamp=now)


# ---------------------------------------------------------------------------
# GET /agents/me — health check / debug
# ---------------------------------------------------------------------------

@router.get("/me")
async def get_me(node: Node = Depends(get_current_node)):
    return {
        "node_id": node.id,
        "hostname": node.hostname,
        "site_id": node.site_id,
        "status": node.status,
        "last_seen": node.last_seen,
    }