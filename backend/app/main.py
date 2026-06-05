import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .infrastructure.database import create_tables
from .services.offline_detector import offline_detector_loop
from .services.heartbeat_cleanup import heartbeat_cleanup_task 
from .api.routes import sites, tokens, agents, nodes, auth

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Setup
    await create_tables()
    
    # Avvia i task in background
    offline_task = asyncio.create_task(offline_detector_loop())
    cleanup_task = asyncio.create_task(heartbeat_cleanup_task(retention_days=7))
    
    yield
    
    # 2. Shutdown: cancella i task correttamente
    offline_task.cancel()
    cleanup_task.cancel()
    
    try:
        await asyncio.gather(offline_task, cleanup_task)
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="EdgeHub API",
    version="0.1.0",
    description="Control plane per fleet di edge nodes eterogenei",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_PREFIX = "/api/v1"
app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(sites.router, prefix=API_PREFIX)
app.include_router(tokens.router, prefix=API_PREFIX)
app.include_router(agents.router, prefix=API_PREFIX)
app.include_router(nodes.router, prefix=API_PREFIX)

@app.get("/health", tags=["system"])
async def health():
    return {"status": "ok", "version": "0.1.0"}