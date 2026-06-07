import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.security import get_admin_session, generate_registration_token
from ...infrastructure.database import get_db
from ...models.registration_token import RegistrationToken
from ...models.site import Site
from ...schemas.token import TokenCreate, TokenResponse, TokenListItem

router = APIRouter(prefix="/sites", tags=["tokens"])

AdminSessionDep = Depends(get_admin_session)

# Helper per generare i comandi
def generate_installation_commands(request: Request, raw_token: str) -> dict:
    return {
        "linux": "curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-linux.sh | sudo bash",
        "docker": "curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-docker.sh | sudo bash",
        "kubernetes": "curl -sSL https://raw.githubusercontent.com/AndreaProzzo21/edge-hub/main/edge-agent/scripts/install-k8s.sh | sudo bash",
    }


@router.post("/{site_id}/tokens", response_model=TokenResponse, status_code=status.HTTP_201_CREATED, dependencies=[AdminSessionDep])
async def create_token(site_id: str, body: TokenCreate, request: Request, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")

    raw_token, token_hash = generate_registration_token()
    db_token = RegistrationToken(
        id=str(uuid.uuid4()),
        site_id=site_id,
        token_hash=token_hash,
        expires_at=RegistrationToken.make_expiry(body.expires_in_hours),
        label=body.label,
    )
    db.add(db_token)
    await db.commit()
    await db.refresh(db_token)

    return TokenResponse(
        id=db_token.id,
        site_id=site_id,
        raw_token=raw_token,
        expires_at=db_token.expires_at,
        label=body.label,
        commands=generate_installation_commands(request, raw_token),
    )


@router.get("/{site_id}/tokens", response_model=list[TokenListItem], dependencies=[AdminSessionDep])
async def list_tokens(site_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(RegistrationToken)
        .where(RegistrationToken.site_id == site_id)
        .order_by(RegistrationToken.expires_at.desc())
    )
    return result.scalars().all()


@router.delete("/{site_id}/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminSessionDep])
async def delete_token(site_id: str, token_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(delete(RegistrationToken).where(RegistrationToken.id == token_id, RegistrationToken.site_id == site_id))
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Token not found")
    await db.commit()