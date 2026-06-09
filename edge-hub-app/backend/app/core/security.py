import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, Security, status, Request
from fastapi.security import APIKeyHeader
from jose import JWTError, jwt

from .config import settings

# ---------------------------------------------------------------------------
# Admin Auth: Sessione Web (Cookie HttpOnly)
# ---------------------------------------------------------------------------

def create_admin_jwt(user_id: str) -> str:
    """Crea un token per la sessione web dell'amministratore."""
    expire = datetime.now(timezone.utc) + timedelta(hours=8)
    payload = {"sub": user_id, "type": "admin", "exp": expire}
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

def decode_admin_jwt(token: str) -> str:
    """Decodifica e valida il token di sessione admin."""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "admin":
        raise JWTError("Invalid token type")
    return payload["sub"]

async def get_admin_session(request: Request) -> str:
    """Dependency per proteggere le route admin tramite Cookie HttpOnly."""
    token = request.cookies.get("admin_access_token")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing session cookie")
    try:
        return decode_admin_jwt(token)
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

# ---------------------------------------------------------------------------
# Admin key: Legacy (mantenuta per script di automazione/test)
# ---------------------------------------------------------------------------

_admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)

async def require_admin_key(key: Optional[str] = Security(_admin_key_header)) -> None:
    """Da usare per script di automazione (test_flow.py) o integrazioni CI/CD."""
    if not key or not secrets.compare_digest(key, settings.ADMIN_API_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Admin-Key header",
        )

# ---------------------------------------------------------------------------
# Registration token helpers (per gli agenti)
# ---------------------------------------------------------------------------

TOKEN_PREFIX = "EDGE_"

def generate_registration_token() -> tuple[str, str]:
    raw = TOKEN_PREFIX + secrets.token_urlsafe(32)
    hashed = _hash_token(raw)
    return raw, hashed

def verify_registration_token(raw_token: str, stored_hash: str) -> bool:
    return secrets.compare_digest(_hash_token(raw_token), stored_hash)

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()

# ---------------------------------------------------------------------------
# Agent JWT helpers
# ---------------------------------------------------------------------------

def create_agent_jwt(node_id: str) -> tuple[str, str, datetime]:
    """Genera il JWT e restituisce: token, JTI (ID univoco) e datetime di scadenza."""
    jti = str(uuid.uuid4())
    expire_dt = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
    
    payload = {
        "sub": node_id,
        "type": "agent",
        "exp": expire_dt,
        "jti": jti,
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, expire_dt

# ECCO LA FUNZIONE RINOMINATA CORRETTAMENTE:
def decode_agent_jwt_full(token: str) -> dict:
    """Restituisce l'intero payload decodificato per poter leggere sub, jti e exp."""
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    if payload.get("type") != "agent":
        raise JWTError("Token type mismatch")
    return payload