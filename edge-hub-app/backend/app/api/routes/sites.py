import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Importiamo la nuova dipendenza per i cookie
from ...core.security import get_admin_session
from ...infrastructure.database import get_db
from ...models.node import Node
from ...models.site import Site
from ...schemas.node import NodeResponse
from ...schemas.site import SiteCreate, SiteResponse

router = APIRouter(prefix="/sites", tags=["sites"])

# Questa dipendenza proteggerà le rotte tramite Cookie HttpOnly
AdminSessionDep = Depends(get_admin_session)

@router.post(
    "/",
    response_model=SiteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[AdminSessionDep],
)
async def create_site(body: SiteCreate, db: AsyncSession = Depends(get_db)):
    site = Site(
        id=str(uuid.uuid4())[:8],
        name=body.name,
        description=body.description,
    )
    db.add(site)
    await db.commit()
    await db.refresh(site)
    return site


@router.get("/", response_model=list[SiteResponse], dependencies=[AdminSessionDep])
async def list_sites(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Site).order_by(Site.created_at.desc()))
    return result.scalars().all()


@router.get("/{site_id}", response_model=SiteResponse, dependencies=[AdminSessionDep])
async def get_site(site_id: str, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    return site


@router.delete("/{site_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[AdminSessionDep])
async def delete_site(site_id: str, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    await db.delete(site)
    await db.commit()


@router.get("/{site_id}/nodes", response_model=list[NodeResponse], dependencies=[AdminSessionDep])
async def list_site_nodes(site_id: str, db: AsyncSession = Depends(get_db)):
    site = await db.get(Site, site_id)
    if not site:
        raise HTTPException(status_code=404, detail="Site not found")
    result = await db.execute(
        select(Node).where(Node.site_id == site_id).order_by(Node.created_at.desc())
    )
    return result.scalars().all()