"""
Webull broker routes — per-user, credential-isolated.

Each request resolves the user's encrypted credentials from the DB and
creates mode-appropriate clients via create_webull_clients().
No user can see another user's account data.

Credentials are loaded from BrokerCredential (legacy) first, then
UserApiConnection (new api-connections system) as fallback.
For unified_mode providers, the same credentials serve both paper and live.
"""

import asyncio
import json
import structlog
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import select

from data.webull import create_webull_clients, WebullClients
from data.webull.trading import OrderRequest as WBOrderRequest
from db.database import get_session
from db.encryption import decrypt_value
from db.models import BrokerCredential, BrokerType, UserApiConnection, ApiProvider

logger = structlog.get_logger(__name__)
router = APIRouter()

# Per-user client cache keyed by (user_id, mode_str)
_client_cache: dict[tuple[int, str], WebullClients] = {}


def invalidate_user_client_cache(user_id: int, mode: Optional[str] = None) -> int:
    """Drop cached Webull clients for a user so fresh credentials are loaded."""
    if mode is not None:
        return int(_client_cache.pop((user_id, mode), None) is not None)

    stale_keys = [cache_key for cache_key in _client_cache if cache_key[0] == user_id]
    for cache_key in stale_keys:
        _client_cache.pop(cache_key, None)
    return len(stale_keys)


async def _get_user_clients(user_id: int, mode: str = "paper") -> Optional[WebullClients]:
    """
    Load or return cached WebullClients for a user and mode.

    Args:
        user_id: The authenticated user.
        mode: "paper" or "real" — determines which Webull host is used.

    Checks BrokerCredential (legacy) first, then UserApiConnection (new system).
    For unified_mode providers the same credentials work for both modes.
    """
    cache_key = (user_id, mode)
    cached = _client_cache.get(cache_key)
    if cached and cached.account._h.connected:
        return cached
    if cached:
        _client_cache.pop(cache_key, None)

    app_key: Optional[str] = None
    app_secret: Optional[str] = None

    # 1. Prefer the current UserApiConnection system.
    async with get_session() as db:
        result = await db.execute(
            select(UserApiConnection)
            .join(ApiProvider)
            .where(
                UserApiConnection.user_id == user_id,
                UserApiConnection.status == "connected",
                ApiProvider.slug == "webull",
            )
        )
        conn = result.scalar_one_or_none()

    if conn:
        try:
            creds = json.loads(decrypt_value(conn.encrypted_credentials))
            app_key = creds.get("app_key", "")
            app_secret = creds.get("app_secret", "")
        except Exception as exc:
            logger.error("webull_cred_decrypt_failed", user_id=user_id, error=str(exc))
            return None
    else:
        # 2. Fall back to legacy BrokerCredential storage for older users.
        async with get_session() as db:
            result = await db.execute(
                select(BrokerCredential).where(
                    BrokerCredential.user_id == user_id,
                    BrokerCredential.broker_type == BrokerType.WEBULL,
                )
            )
            cred = result.scalar_one_or_none()

        if not cred:
            return None

        app_key = decrypt_value(cred.encrypted_api_key)
        app_secret = decrypt_value(cred.encrypted_api_secret)

    if not app_key or not app_secret:
        return None

    try:
        clients = create_webull_clients(
            mode,
            app_key=app_key,
            app_secret=app_secret,
        )
        _client_cache[cache_key] = clients
        logger.info("webull_clients_loaded", user_id=user_id, mode=mode)
        return clients

    except RuntimeError as exc:
        # Real-mode guardrails not met on this server — surface clearly
        logger.error("webull_real_mode_blocked", user_id=user_id, error=str(exc))
        return None
    except Exception as exc:
        logger.error("webull_client_error", user_id=user_id, error=str(exc))
        return None


# ── Request models ────────────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    symbol:         str
    side:           str              # "BUY" | "SELL"
    qty:            int = 1
    order_type:     str = "MKT"      # "MKT" | "LMT" | "STP" | "STP_LMT"
    limit_price:    Optional[float] = None
    stop_price:     Optional[float] = None
    tif:            str = "DAY"
    user_confirmed: bool = False


# ── Routes ────────────────────────────────────────────────────────────────────

def _mode_str(request: Request) -> str:
    """Map the middleware's TradingModeEnum to the Webull SDK's mode string."""
    from db.models import TradingModeEnum
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
    return "real" if mode == TradingModeEnum.LIVE else "paper"


@router.get("/status")
async def webull_status(request: Request):
    """Check if the authenticated user has a connected Webull account."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        return {"connected": False}

    result = await asyncio.to_thread(clients.account._h.connect)
    if not result.get("success"):
        return {"connected": False, "error": result.get("error")}

    return {
        "connected": True,
        "mode":       clients.mode.value,
        "account_id": clients.account._h.allowed_account,
    }


@router.get("/account")
async def webull_account(request: Request):
    """Account summary — only returns the authenticated user's account."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        return {"connected": False, "error": "No Webull credentials configured"}

    summary = await asyncio.to_thread(clients.account.get_summary)
    if not summary:
        invalidate_user_client_cache(request.state.user_id, _mode_str(request))
        return {"connected": True, "error": "Could not fetch account data"}
    return {"connected": True, **summary}


@router.get("/positions")
async def webull_positions(request: Request):
    """Open positions — only the authenticated user's positions."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        return {"connected": False, "positions": []}

    positions = await asyncio.to_thread(clients.account.get_positions)
    return {"connected": True, "positions": positions}


@router.get("/orders")
async def webull_orders(request: Request):
    """Open orders — only the authenticated user's orders."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        return {"connected": False, "orders": []}

    orders = await asyncio.to_thread(clients.account.get_open_orders)
    return {"connected": True, "orders": orders}


@router.get("/quotes")
async def webull_quotes(
    request: Request,
    symbols: str = Query(default="SPY,QQQ,AAPL,TSLA,NVDA,MSFT,AMZN,META"),
):
    """
    Stock quotes. Falls back to unofficial SDK if user has no Webull credentials.
    (Quotes are public market data — auth not strictly required.)
    """
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    clients     = await _get_user_clients(request.state.user_id, _mode_str(request))

    if clients:
        quotes = await asyncio.to_thread(clients.market_data.get_quotes, symbol_list)
        return {"connected": True, "quotes": quotes}

    # Fallback: unofficial SDK (no auth required for US equity quotes)
    try:
        def _fetch_public_quotes() -> dict[str, dict]:
            from webull import webull

            wb = webull()
            quotes: dict[str, dict] = {}
            for sym in symbol_list:
                raw = wb.get_quote(sym)
                if raw:
                    quotes[sym] = {
                        "symbol": sym,
                        "price": float(raw.get("close", 0)),
                        "change": float(raw.get("change", 0)),
                        "change_pct": float(raw.get("changeRatio", 0)) * 100,
                        "volume": int(float(raw.get("volume", 0))),
                        "open": float(raw.get("open", 0)),
                        "high": float(raw.get("high", 0)),
                        "low": float(raw.get("low", 0)),
                        "prev_close": float(raw.get("preClose", 0)),
                    }
            return quotes

        quotes = await asyncio.to_thread(_fetch_public_quotes)
        return {"connected": False, "quotes": quotes}
    except Exception as exc:
        logger.warning("quote_fallback_failed", error=str(exc))
        return {"connected": False, "quotes": {}}


@router.post("/order")
async def webull_place_order(req: PlaceOrderRequest, request: Request):
    """Place an order — requires explicit user_confirmed=True."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        raise HTTPException(status_code=400, detail="No Webull credentials configured")

    wb_req = WBOrderRequest(
        symbol=req.symbol.upper(),
        side=req.side.upper(),
        qty=req.qty,
        order_type=req.order_type.upper(),
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        tif=req.tif.upper(),
    )

    result = await asyncio.to_thread(
        clients.trading.place_order,
        wb_req,
        user_confirmed=req.user_confirmed,
    )

    if result.success:
        logger.info(
            "webull_order_accepted",
            user_id=request.state.user_id,
            symbol=req.symbol,
            side=req.side,
            qty=req.qty,
            order_id=result.order_id,
            mode=result.mode,
        )
        return {
            "success":         True,
            "order_id":        result.order_id,
            "client_order_id": result.client_order_id,
            "mode":            result.mode,
        }

    raise HTTPException(status_code=400, detail=result.error)


@router.delete("/order/{client_order_id}")
async def webull_cancel_order(client_order_id: str, request: Request):
    """Cancel an open order."""
    clients = await _get_user_clients(request.state.user_id, _mode_str(request))
    if not clients:
        raise HTTPException(status_code=400, detail="No Webull credentials configured")

    result = clients.trading.cancel_order(client_order_id)
    if result.success:
        return {"success": True}
    raise HTTPException(status_code=400, detail=result.error)
