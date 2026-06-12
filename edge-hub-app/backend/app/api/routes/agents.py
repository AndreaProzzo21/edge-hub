import hashlib
import uuid
import asyncio
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from ...core.security import create_agent_jwt, decode_agent_jwt_full
from ...infrastructure.database import get_db
from ...models.heartbeat import Heartbeat
from ...models.node import Node, NodeStatus
from ...models.registration_token import RegistrationToken
from ...models.site import Site
from ...schemas.agent import AgentRegisterRequest, AgentRegisterResponse
from ...schemas.heartbeat import HeartbeatRequest, HeartbeatResponse
from ...services.alert_engine import dispatch_recovery_alerts, dispatch_metric_alert
from .websockets import ws_manager

router = APIRouter(prefix="/agents", tags=["agents"])
bearer = HTTPBearer()

# ---------------------------------------------------------------------------
# Dependency: La "Ghigliottina" con controllo Rolling JTI
# ---------------------------------------------------------------------------
async def get_current_node(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: AsyncSession = Depends(get_db),
) -> Node:
    try:
        # Decodifichiamo l'intero payload
        payload = decode_agent_jwt_full(credentials.credentials)
        node_id = payload["sub"]
        token_jti = payload.get("jti")
        token_exp = payload.get("exp")
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

    # --- LOGICA DI REVOCA ROLLING JTI ---
    if not token_jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Legacy token without JTI is no longer supported"
        )

    if token_jti == node.active_jti:
        pass # Tutto ok, sta usando il token attivo
    elif token_jti == node.pending_jti:
        # L'agente ha usato il NUOVO token per la prima volta!
        # Consolidiamo lo stato: il pendente diventa l'attivo.
        node.active_jti = node.pending_jti
        node.pending_jti = None
        if token_exp:
            node.jwt_expires_at = datetime.fromtimestamp(token_exp, timezone.utc)
        await db.commit() # Salviamo subito il cambio di stato
    else:
        # Il token è crittograficamente valido, ma il suo JTI non è autorizzato.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Token has been explicitly revoked"
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
    await db.flush() # Flush per assicurarci che il nodo sia pronto

    # 4. Emetti il JWT dell'agente e salva JTI e Scadenza
    agent_token, jti, expire_dt = create_agent_jwt(node.id)
    node.active_jti = jti
    node.jwt_expires_at = expire_dt
    
    await db.commit()
    await db.refresh(node)

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

ALERT_THRESHOLDS = {
    "cpu": 80.0,
    "temp": 70.0,
    "disk": 70.0,
}
COOLDOWN_MINUTES = 60


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(
    body: HeartbeatRequest,
    background_tasks: BackgroundTasks,
    node: Node = Depends(get_current_node),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.now(timezone.utc)

    # 1. Salvataggio record storico
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

    # 2. Aggiornamento stato del nodo
    node.last_seen = now
    node.status = NodeStatus.ONLINE
    node.cpu_usage = body.cpu_usage
    node.mem_usage = body.memory_usage
    node.uptime_seconds = body.uptime_seconds

    # --- LOGICA ALERT ENGINE: OFFLINE & RECOVERY ---
    offline_cycles = getattr(node, "offline_cycles", 0)
    offline_alert_sent = getattr(node, "offline_alert_sent", False)

    if offline_cycles > 0 or offline_alert_sent:
        if offline_alert_sent:
            site = await db.get(Site, node.site_id)
            if site:
                background_tasks.add_task(dispatch_recovery_alerts, node, site)

        node.offline_cycles = 0
        node.offline_alert_sent = False

    # --- LOGICA ALERT ENGINE: METRICHE IN SOFFERENZA (CPU, TEMP, DISK) ---
    alerts_to_send = []
    current_temp = body.extra_data.get("cpu_temp_celsius", 0.0) if body.extra_data else 0.0

    metrics_to_check = {
        "cpu": body.cpu_usage,
        "disk": body.disk_usage,
        "temp": current_temp,
    }

    current_timestamps = getattr(node, "last_alert_timestamps", {})
    if not isinstance(current_timestamps, dict):
        current_timestamps = {}

    new_timestamps = dict(current_timestamps)
    now_unix = now.timestamp()

    for m_type, val in metrics_to_check.items():
        if val is not None and val >= ALERT_THRESHOLDS[m_type]:
            last_alert_unix = new_timestamps.get(m_type)
            can_send = True

            if last_alert_unix is not None:
                try:
                    if now_unix < float(last_alert_unix) + (COOLDOWN_MINUTES * 60):
                        can_send = False
                except (ValueError, TypeError):
                    pass

            if can_send:
                alerts_to_send.append((m_type, val, ALERT_THRESHOLDS[m_type]))
                new_timestamps[m_type] = now_unix

    if alerts_to_send:
        node.last_alert_timestamps = new_timestamps
        flag_modified(node, "last_alert_timestamps")

        # ✅ db.get usa la identity map: se il sito è già stato caricato sopra
        #    nel blocco recovery, non fa una seconda query al DB.
        site = await db.get(Site, node.site_id)
        if site:
            node_hostname       = node.hostname
            node_id             = node.id
            site_name           = site.name
            discord_webhook_url = site.discord_webhook_url
            slack_webhook_url   = site.slack_webhook_url

            for m_type, val, thresh in alerts_to_send:
                background_tasks.add_task(
                    dispatch_metric_alert,
                    node_hostname,
                    node_id,
                    site_name,
                    discord_webhook_url,
                    slack_webhook_url,
                    m_type.upper(),
                    val,
                    thresh,
                )

    # --- LOGICA: COMMAND & CONTROL ---
    command_to_send = None
    if getattr(node, "pending_command", None):
        command_to_send = node.pending_command
        node.pending_command = None

    await db.commit()

    # --- BROADCAST WEBSOCKET ---
    task = asyncio.create_task(ws_manager.broadcast(node.site_id, {
        "event_type": "heartbeat",
        "timestamp": now.isoformat(),
        "node_id": node.id,
        "hostname": node.hostname,
        "telemetry": {
            "cpu_usage": body.cpu_usage,
            "memory_usage": body.memory_usage,
            "disk_usage": body.disk_usage,
        },
    }))
    task.add_done_callback(
        lambda t: print(f"WS broadcast failed for node {node.id}: {t.exception()}")
        if t.exception() else None
    )

    return HeartbeatResponse(
        node_id=node.id,
        timestamp=now,
        command=command_to_send,
    )

@router.get("/me")
async def get_me(node: Node = Depends(get_current_node)):
    return {
        "node_id": node.id,
        "hostname": node.hostname,
        "site_id": node.site_id,
        "status": node.status,
        "last_seen": node.last_seen,
    }