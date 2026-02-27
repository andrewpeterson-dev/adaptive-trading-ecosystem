"""
FastAPI application — main entry point for the trading ecosystem API.
"""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import trading, models as models_routes, dashboard, system
from config.settings import get_settings
from db.database import init_db, close_db

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    logger.info("starting_trading_ecosystem", mode=settings.trading_mode.value)
    await init_db()
    yield
    await close_db()
    logger.info("trading_ecosystem_stopped")


app = FastAPI(
    title="Adaptive Trading Ecosystem",
    description="Multi-model adaptive AI trading platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount route modules
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(models_routes.router, prefix="/api/models", tags=["Models"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(system.router, prefix="/api/system", tags=["System"])


@app.get("/health")
async def health_check():
    settings = get_settings()
    return {
        "status": "healthy",
        "mode": settings.trading_mode.value,
        "version": "1.0.0",
    }
