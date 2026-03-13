"""
Ledger routes — combined broker + options sim equity view.
"""
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import select
import structlog

from db.cerberus_models import CerberusPortfolioSnapshot
from db.database import get_session
from db.models import UserApiSettings, UserApiConnection, ApiProvider, PortfolioSnapshot
from services.ledger_aggregator import ledger_aggregator
from services.api_connection_manager import api_connection_manager

logger = structlog.get_logger(__name__)
router = APIRouter()


def _require_user(request: Request) -> int:
    user_id = getattr(request.state, "user_id", None)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user_id


def _series_payload(values: Sequence[float]) -> tuple[float, float, list[float]]:
    clean = [float(value) for value in values if value is not None]
    if not clean:
        return 0.0, 0.0, []
    return clean[-1], clean[0], clean


async def _load_cerberus_equity_series(user_id: int) -> tuple[float, float, list[float]]:
    async with get_session() as db:
        result = await db.execute(
            select(CerberusPortfolioSnapshot)
            .where(CerberusPortfolioSnapshot.user_id == user_id)
            .order_by(CerberusPortfolioSnapshot.snapshot_ts.desc())
            .limit(120)
        )
        snapshots = list(reversed(result.scalars().all()))
    return _series_payload([snap.equity for snap in snapshots if snap.equity is not None])


async def _load_core_equity_series(user_id: int, mode) -> tuple[float, float, list[float]]:
    async with get_session() as db:
        result = await db.execute(
            select(PortfolioSnapshot)
            .where(
                PortfolioSnapshot.mode == mode,
                PortfolioSnapshot.user_id == user_id,
            )
            .order_by(PortfolioSnapshot.timestamp.desc())
            .limit(120)
        )
        snapshots = list(reversed(result.scalars().all()))
    return _series_payload([snap.total_equity for snap in snapshots if snap.total_equity is not None])


@router.get("/ledger/combined")
async def get_combined_ledger(request: Request):
    """
    Returns combined equity from active broker + options sim P&L.
    Always safe to call: if no options fallback, options_sim_pnl=0.
    """
    user_id = _require_user(request)
    settings = await api_connection_manager.get_or_create_settings(user_id)
    mode = getattr(request.state, "trading_mode", None)

    broker_equity, initial_equity, equity_series = await _load_cerberus_equity_series(user_id)
    if not equity_series and mode is not None:
        broker_equity, initial_equity, equity_series = await _load_core_equity_series(user_id, mode)

    broker_label = "No Broker Connected"

    if settings.active_equity_broker_id:
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.active_equity_broker_id,
                    UserApiConnection.user_id == user_id,
                )
            )
            conn = r.scalar_one_or_none()
            if conn:
                broker_label = f"{conn.provider.name} ({'Paper' if conn.is_paper else 'Live'})"
    elif equity_series:
        broker_label = "Stored Portfolio Snapshot"

    options_label = None
    if getattr(settings, "options_fallback_enabled", False) and getattr(settings, "options_provider_connection_id", None):
        async with get_session() as db:
            r = await db.execute(
                select(UserApiConnection).join(ApiProvider).where(
                    UserApiConnection.id == settings.options_provider_connection_id,
                    UserApiConnection.user_id == user_id,
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
        equity_series=equity_series,
        options_label=options_label,
        options_fallback_enabled=getattr(settings, "options_fallback_enabled", False),
    )
