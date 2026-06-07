import json
import logging
from collections import defaultdict
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status
from jose import JWTError
from ...core.security import decode_admin_jwt

logger = logging.getLogger(__name__)

class ConnectionManager:
    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket, site_id: str):
        await websocket.accept()
        self.active_connections[site_id].append(websocket)
        logger.info(f"WebSocket connected for site: {site_id}. Total: {len(self.active_connections[site_id])}")

    def disconnect(self, websocket: WebSocket, site_id: str):
        if websocket in self.active_connections[site_id]:
            self.active_connections[site_id].remove(websocket)
            logger.info(f"WebSocket disconnected for site: {site_id}.")

    async def broadcast(self, site_id: str, message: dict):
        if site_id not in self.active_connections:
            return

        dead_sockets = []
        for connection in self.active_connections[site_id]:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Error sending message to websocket: {e}")
                dead_sockets.append(connection)
        
        for dead in dead_sockets:
            self.disconnect(dead, site_id)

ws_manager = ConnectionManager()
router = APIRouter(prefix="/ws", tags=["websockets"])

@router.websocket("/sites/{site_id}/stream")
async def websocket_endpoint(websocket: WebSocket, site_id: str):
    # 1. Recupera il cookie manualmente dall'handshake
    cookies = websocket.cookies
    token = cookies.get("admin_access_token")

    # 2. Validazione sicurezza
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    try:
        # Riutilizziamo la tua funzione di decodifica esistente
        admin_id = decode_admin_jwt(token)
    except JWTError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # 3. Connessione avvenuta con successo
    await ws_manager.connect(websocket, site_id)
    try:
        while True:
            # Manteniamo la connessione viva finché il client non chiude
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, site_id)