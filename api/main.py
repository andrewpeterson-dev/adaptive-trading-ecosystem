"""
FastAPI application — main entry point for the trading ecosystem API.
"""

import asyncio
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes import trading, models as models_routes, dashboard, system, strategies, explainer, news
from api.routes import auth as auth_routes, webull as webull_routes
from api.routes import admin as admin_routes
from api.routes import api_connections as api_connections_routes
from api.routes import llm_status
from api.routes import lighthouse as lighthouse_routes
from api.routes import auto_loop as auto_loop_routes
from api.routes import intelligence as intelligence_routes
from api.routes import paper_trading as paper_routes
from api.routes import market as market_routes
from api.routes import ws as ws_routes
from api.routes import ai_chat, ai_tools, documents as documents_routes
from api.routes import user_mode as user_mode_routes
from api.routes import risk_limits as risk_limits_routes
from api.routes import quant as quant_routes
from api.routes import reasoning as reasoning_routes
from api.middleware.auth import JWTAuthMiddleware
from api.middleware.trading_mode import TradingModeMiddleware
from config.settings import get_settings
from db.database import init_db, close_db

logger = structlog.get_logger(__name__)
_db_init_state = {"ready": False, "failed": False}


def _spawn_background_task(
    tasks: set[asyncio.Task],
    *,
    coro,
    name: str,
) -> asyncio.Task:
    task = asyncio.create_task(coro, name=name)
    tasks.add(task)

    def _on_done(done_task: asyncio.Task) -> None:
        tasks.discard(done_task)
        try:
            done_task.result()
        except asyncio.CancelledError:
            logger.info("background_task_cancelled", task=name)
        except Exception as exc:  # pragma: no cover - defensive background logging
            logger.exception("background_task_failed", task=name, error=str(exc))

    task.add_done_callback(_on_done)
    return task


def _validate_env(settings) -> None:
    """Validate environment variables at startup. Warns on missing optional vars."""
    critical = {
        "jwt_secret": settings.jwt_secret,
        "encryption_key": settings.encryption_key,
    }
    for name, value in critical.items():
        if not value or value in ("ate-dev-secret-change-in-production", ""):
            logger.warning("env_var_default_or_missing", var=name,
                           hint=f"Set {name.upper()} in .env for production")

    optional = {
        "alpaca_api_key": settings.alpaca_api_key,
        "anthropic_api_key": settings.anthropic_api_key,
        "finnhub_api_key": settings.finnhub_api_key,
        "alphavantage_api_key": settings.alphavantage_api_key,
        "smtp_user": settings.smtp_user,
    }
    configured = [k for k, v in optional.items() if v]
    missing = [k for k, v in optional.items() if not v]
    if configured:
        logger.info("configured_services", services=configured)
    if missing:
        logger.info("unconfigured_services", services=missing,
                     hint="These features will be unavailable")

    logger.info("trading_config",
                mode=settings.trading_mode.value,
                live_enabled=settings.live_trading_enabled,
                use_sqlite=settings.use_sqlite,
                auto_loop=settings.auto_loop_enabled)


async def _init_db_with_retry() -> None:
    """Initialize DB in the background with retries so startup never blocks the healthcheck."""
    _db_init_state["ready"] = False
    _db_init_state["failed"] = False
    for attempt in range(10):
        try:
            await init_db()
            _db_init_state["ready"] = True
            _db_init_state["failed"] = False
            logger.info("db_initialized", attempt=attempt + 1)
            return
        except Exception as exc:
            _db_init_state["ready"] = False
            wait = min(5 * (attempt + 1), 30)
            logger.warning("db_init_retry", attempt=attempt + 1, error=str(exc), retry_in=wait)
            await asyncio.sleep(wait)
    _db_init_state["failed"] = True
    logger.error("db_init_failed_permanently")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    settings = get_settings()
    background_tasks: set[asyncio.Task] = set()
    _db_init_state["ready"] = False
    _db_init_state["failed"] = False
    _validate_env(settings)
    logger.info("starting_trading_ecosystem", mode=settings.trading_mode.value)
    # Non-blocking: DB init runs in background so /health responds immediately.
    # This prevents Railway's 30s healthcheck from expiring during DB connection.
    _spawn_background_task(background_tasks, coro=_init_db_with_retry(), name="db_init_with_retry")

    # Register all Cerberus AI tools so the chat controller can use them
    from services.ai_core.tools.register_all import register_all_tools
    register_all_tools()

    # Start the bot execution engine (evaluates running bots every 60s)
    from services.bot_engine.runner import bot_runner
    from services.strategy_learning_engine import StrategyLearningEngine
    from services.context_monitor import ContextMonitor
    from services.universe_scanner import UniverseScanner

    learning_engine = StrategyLearningEngine()
    context_monitor = ContextMonitor()
    universe_scanner = UniverseScanner()
    _spawn_background_task(background_tasks, coro=bot_runner.start(), name="bot_runner")
    _spawn_background_task(background_tasks, coro=learning_engine.start(), name="strategy_learning_engine")
    _spawn_background_task(background_tasks, coro=context_monitor.start(), name="context_monitor")
    _spawn_background_task(background_tasks, coro=universe_scanner.start(), name="universe_scanner")

    yield

    # Shutdown
    await bot_runner.stop()
    await learning_engine.stop()
    await context_monitor.stop()
    await universe_scanner.stop()
    if background_tasks:
        await asyncio.gather(*background_tasks, return_exceptions=True)
    await close_db()
    logger.info("trading_ecosystem_stopped")


app = FastAPI(
    title="Adaptive Trading Ecosystem",
    description="Multi-model adaptive AI trading platform",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(TradingModeMiddleware)
app.add_middleware(JWTAuthMiddleware)

_settings = get_settings()
_cors_origins = [o.strip() for o in _settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Security headers middleware
@app.middleware("http")
async def security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if _settings.base_url.startswith("https://"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# Mount route modules
app.include_router(auth_routes.router, prefix="/api/auth", tags=["Auth"])
app.include_router(webull_routes.router, prefix="/api/webull", tags=["Webull"])
app.include_router(trading.router, prefix="/api/trading", tags=["Trading"])
app.include_router(models_routes.router, prefix="/api/models", tags=["Models"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["Dashboard"])
app.include_router(system.router, prefix="/api/system", tags=["System"])
app.include_router(strategies.router, prefix="/api", tags=["Strategies"])
app.include_router(explainer.router, prefix="/api", tags=["Explainer"])
app.include_router(news.router, prefix="/api/news", tags=["News"])
app.include_router(llm_status.router, prefix="/api/system", tags=["System"])
app.include_router(lighthouse_routes.router, prefix="/api/system", tags=["Lighthouse"])
app.include_router(auto_loop_routes.router, prefix="/api/system", tags=["Auto-Loop"])
app.include_router(intelligence_routes.router, prefix="/api/intelligence", tags=["Intelligence"])
app.include_router(paper_routes.router, prefix="/api/paper", tags=["Paper Trading"])
app.include_router(admin_routes.router, prefix="/api/admin", tags=["Admin"])
app.include_router(api_connections_routes.router, prefix="/api/v2", tags=["api-connections"])
from api.routes import ledger as ledger_routes
app.include_router(ledger_routes.router, prefix="/api/v2", tags=["ledger"])
app.include_router(market_routes.router, prefix="/api/market", tags=["Market Data"])
app.include_router(ws_routes.router, prefix="/ws", tags=["WebSocket"])
app.include_router(ai_chat.router, prefix="/api/ai", tags=["Cerberus"])
app.include_router(ai_tools.router, prefix="/api/ai/tools", tags=["Cerberus Tools"])
app.include_router(documents_routes.router, prefix="/api/documents", tags=["Documents"])
app.include_router(user_mode_routes.router, prefix="/api/user", tags=["User"])
app.include_router(risk_limits_routes.router, prefix="/api/risk", tags=["Risk"])
app.include_router(quant_routes.router, prefix="/api/quant", tags=["Quant Intelligence"])
app.include_router(reasoning_routes.router, prefix="/api/reasoning", tags=["AI Reasoning"])


@app.get("/health")
async def health_check():
    """Lightweight liveness probe — always returns 200 if the app is running."""
    return {
        "status": "ok",
        "ready": _db_init_state["ready"],
        "database": "ready" if _db_init_state["ready"] else ("failed" if _db_init_state["failed"] else "starting"),
    }


@app.get("/health/ready")
async def readiness_check():
    """Readiness probe — returns 503 until critical startup tasks are complete."""
    if _db_init_state["ready"]:
        return {"status": "ready", "database": "ready"}
    return JSONResponse(
        status_code=503,
        content={
            "status": "not_ready",
            "database": "failed" if _db_init_state["failed"] else "starting",
        },
    )


@app.get("/health/detailed")
async def health_check_detailed():
    """Comprehensive health check — database, Redis, broker, disk, memory."""
    from monitor.health_check import HealthChecker

    checker = HealthChecker()
    return await checker.check_all()
