"""
Webull broker routes — per-user, credential-isolated.

Each request resolves the user's encrypted credentials from the DB and
creates mode-appropriate clients via create_webull_clients().
No user can see another user's account data.
"""

import structlog
from typing import Optional

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import select

from data.webull import create_webull_clients, WebullClients
from data.webull.trading import OrderRequest as WBOrderRequest
from db.database import get_session
from db.encryption import decrypt_value
from db.models import BrokerCredential, BrokerType

logger = structlog.get_logger(__name__)
router = APIRouter()

# Per-user client cache: {user_id: WebullClients}
_client_cache: dict[int, WebullClients] = {}


async def _get_user_clients(user_id: int) -> Optional[WebullClients]:
    """
    Load or return cached WebullClients for a user.
    Clients are cached while connected; expired/disconnected entries are re-created.
    """
    cached = _client_cache.get(user_id)
    if cached and cached.account._h.connected:
        return cached

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

    try:
        app_key    = decrypt_value(cred.encrypted_api_key)
        app_secret = decrypt_value(cred.encrypted_api_secret)
        mode       = "paper" if cred.is_paper else "real"

        clients = create_webull_clients(
            mode,
            app_key=app_key,
            app_secret=app_secret,
        )
        _client_cache[user_id] = clients
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

@router.get("/status")
async def webull_status(request: Request):
    """Check if the authenticated user has a connected Webull account."""
    clients = await _get_user_clients(request.state.user_id)
    if not clients:
        return {"connected": False}

    result = clients.account._h.connect()
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
    clients = await _get_user_clients(request.state.user_id)
    if not clients:
        return {"connected": False, "error": "No Webull credentials configured"}

    summary = clients.account.get_summary()
    if not summary:
        return {"connected": True, "error": "Could not fetch account data"}
    return {"connected": True, **summary}


@router.get("/positions")
async def webull_positions(request: Request):
    """Open positions — only the authenticated user's positions."""
    clients = await _get_user_clients(request.state.user_id)
    if not clients:
        return {"connected": False, "positions": []}

    return {"connected": True, "positions": clients.account.get_positions()}


@router.get("/orders")
async def webull_orders(request: Request):
    """Open orders — only the authenticated user's orders."""
    clients = await _get_user_clients(request.state.user_id)
    if not clients:
        return {"connected": False, "orders": []}

    return {"connected": True, "orders": clients.account.get_open_orders()}


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
    clients     = await _get_user_clients(request.state.user_id)

    if clients:
        quotes = clients.market_data.get_quotes(symbol_list)
        return {"connected": True, "quotes": quotes}

    # Fallback: unofficial SDK (no auth required for US equity quotes)
    try:
        from webull import webull
        wb     = webull()
        quotes = {}
        for sym in symbol_list:
            raw = wb.get_quote(sym)
            if raw:
                quotes[sym] = {
                    "symbol":     sym,
                    "price":      float(raw.get("close", 0)),
                    "change":     float(raw.get("change", 0)),
                    "change_pct": float(raw.get("changeRatio", 0)) * 100,
                    "volume":     int(float(raw.get("volume", 0))),
                    "open":       float(raw.get("open", 0)),
                    "high":       float(raw.get("high", 0)),
                    "low":        float(raw.get("low", 0)),
                    "prev_close": float(raw.get("preClose", 0)),
                }
        return {"connected": False, "quotes": quotes}
    except Exception as exc:
        logger.warning("quote_fallback_failed", error=str(exc))
        return {"connected": False, "quotes": {}}


@router.post("/order")
async def webull_place_order(req: PlaceOrderRequest, request: Request):
    """Place an order — requires explicit user_confirmed=True."""
    clients = await _get_user_clients(request.state.user_id)
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

    result = clients.trading.place_order(wb_req, user_confirmed=req.user_confirmed)

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
    clients = await _get_user_clients(request.state.user_id)
    if not clients:
        raise HTTPException(status_code=400, detail="No Webull credentials configured")

    result = clients.trading.cancel_order(client_order_id)
    if result.success:
        return {"success": True}
    raise HTTPException(status_code=400, detail=result.error)
