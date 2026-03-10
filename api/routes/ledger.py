"""
Ledger routes — combined broker + options sim equity view.
"""
from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
import structlog

from db.database import get_session
from db.models import UserApiSettings, UserApiConnection, ApiProvider
from services.ledger_aggregator import ledger_aggregator
from services.api_connection_manager import api_connection_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


def _require_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


@router.get("/ledger/combined")
async def get_combined_ledger(request: Request):
    """
    Returns combined equity from active broker + options sim P&L.
    Always safe to call: if no options fallback, options_sim_pnl=0.
    """
    user_id = _require_user(request)
    settings = await api_connection_manager.get_or_create_settings(user_id)

    broker_equity = 1_000_000.0
    broker_label = "No Broker Connected"
    initial_equity = 1_000_000.0

    if settings.active_equity_broker_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.active_equity_broker_id
                )
            )
            conn = r.scalar_one_or_none()
            if conn:
                broker_label = f"{conn.provider.name} ({'Paper' if conn.is_paper else 'Live'})"

    options_label = None
    if getattr(settings, "options_fallback_enabled", False) and getattr(settings, "options_provider_connection_id", None):
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.options_provider_connection_id
                )
            )
            conn = r.scalar_one_or_none()
            if conn:
                options_label = f"{conn.provider.name} (Options Sim)"

    return await ledger_aggregator.build_combined(
        user_id=user_id,
        broker_equity=broker_equity,
        broker_label=broker_label,
        initial_equity=initial_equity,
        options_label=options_label,
        options_fallback_enabled=getattr(settings, "options_fallback_enabled", False),
    )
