"""
Webull broker routes — per-user, credential-isolated.

Each user's Webull client is loaded from their encrypted credentials in the DB.
Users without Webull credentials get {"connected": false} responses.
No user can see another user's account data.
"""

import structlog
from typing import Optional
from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel
from sqlalchemy import select

from db.database import get_session
from db.encryption import decrypt_value
from db.models import BrokerCredential, BrokerType

logger = structlog.get_logger(__name__)
router = APIRouter()

# Per-user client cache: {user_id: WebullLiveClient}
_client_cache: dict[int, object] = {}


async def _get_user_webull_client(user_id: int):
    """Load or return cached Webull client for a specific user."""
    if user_id in _client_cache:
        client = _client_cache[user_id]
        if client.is_connected:
            return client

    # Load credentials from DB
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
        from data.webull_client import WebullLiveClient, WebullPaperClient
        app_key = decrypt_value(cred.encrypted_api_key)
        app_secret = decrypt_value(cred.encrypted_api_secret)
        if cred.is_paper:
            client = WebullPaperClient(app_key=app_key, app_secret=app_secret)
        else:
            client = WebullLiveClient(app_key=app_key, app_secret=app_secret)
        connect_result = client.connect()
        if connect_result.get("success"):
            _client_cache[user_id] = client
            account_id = client._get_allowed_account_id()
            if not account_id:
                logger.warning("webull_connected_no_account_id", user_id=user_id,
                               paper_accounts=len(client._paper_account_ids),
                               live_accounts=len(client._live_account_ids),
                               mode=connect_result.get("mode"))
            else:
                logger.info("webull_client_cached", user_id=user_id, account_id=account_id)
            return client
        else:
            logger.warning("webull_connect_failed", user_id=user_id, error=connect_result.get("error"))
            return None
    except Exception as e:
        logger.error("webull_client_error", user_id=user_id, error=str(e))
        return None


# ── Request Models ───────────────────────────────────────────────────────

class PlaceOrderRequest(BaseModel):
    symbol: str
    side: str  # "BUY" or "SELL"
    qty: int = 1
    order_type: str = "MKT"  # "MKT", "LMT", "STP"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = "DAY"
    user_confirmed: bool = False


# ── Routes ───────────────────────────────────────────────────────────────

@router.get("/status")
async def webull_status(request: Request):
    """Check if user has a connected Webull account with accessible data."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        return {"connected": False}
    account_id = client._get_allowed_account_id()
    if not account_id:
        return {"connected": False, "error": "Broker authenticated but no account found — check that your API key has account access."}
    summary = client.get_account_summary()
    if not summary:
        return {"connected": False, "error": "Connected but could not fetch account data — API key may lack account permissions."}
    return {
        "connected": True,
        "mode": client.mode_label,
        "account_id": account_id,
    }


@router.get("/account")
async def webull_account(request: Request):
    """Get account summary — only returns the authenticated user's account."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        return {"connected": False, "error": "No Webull credentials configured"}

    summary = client.get_account_summary()
    if not summary:
        return {"connected": True, "error": "Could not fetch account data"}
    return {"connected": True, **summary}


@router.get("/positions")
async def webull_positions(request: Request):
    """Get open positions — only the authenticated user's positions."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        return {"connected": False, "positions": []}

    positions = client.get_positions()
    return {"connected": True, "positions": positions}


@router.get("/orders")
async def webull_orders(request: Request):
    """Get open orders — only the authenticated user's orders."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        return {"connected": False, "orders": []}

    orders = client.get_open_orders()
    return {"connected": True, "orders": orders}


@router.get("/quotes")
async def webull_quotes(
    request: Request,
    symbols: str = Query(default="SPY,QQQ,AAPL,TSLA,NVDA,MSFT,AMZN,META"),
):
    """Get stock quotes. Works for any authenticated user (quotes are public data)."""
    client = await _get_user_webull_client(request.state.user_id)

    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]

    if client:
        quotes = client.get_quotes(symbol_list)
        return {"connected": True, "quotes": quotes}

    # Fallback: use unofficial webull SDK for quotes (no auth needed)
    try:
        from webull import webull
        wb = webull()
        quotes = {}
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
        return {"connected": False, "quotes": quotes}
    except Exception as e:
        logger.warning("quote_fallback_failed", error=str(e))
        return {"connected": False, "quotes": {}}


@router.post("/order")
async def webull_place_order(req: PlaceOrderRequest, request: Request):
    """Place an order — requires explicit user_confirmed=True."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        raise HTTPException(status_code=400, detail="No Webull credentials configured")

    if not req.user_confirmed:
        raise HTTPException(status_code=400, detail="Order requires explicit confirmation (user_confirmed=true)")

    result = client.place_order(
        symbol=req.symbol.upper(),
        side=req.side.upper(),
        qty=req.qty,
        order_type=req.order_type.upper(),
        limit_price=req.limit_price,
        stop_price=req.stop_price,
        tif=req.tif.upper(),
        user_confirmed=True,
    )

    if result.get("success"):
        logger.info("webull_order_placed",
                     user_id=request.state.user_id,
                     symbol=req.symbol, side=req.side, qty=req.qty)
        return result
    else:
        raise HTTPException(status_code=400, detail=result.get("error", "Order failed"))


@router.delete("/order/{client_order_id}")
async def webull_cancel_order(client_order_id: str, request: Request):
    """Cancel an open order."""
    client = await _get_user_webull_client(request.state.user_id)
    if not client:
        raise HTTPException(status_code=400, detail="No Webull credentials configured")

    result = client.cancel_order(client_order_id)
    if result.get("success"):
        return {"success": True}
    raise HTTPException(status_code=400, detail=result.get("error", "Cancel failed"))
