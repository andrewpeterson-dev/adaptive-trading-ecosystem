from __future__ import annotations

"""
Trading endpoints — execute signals, manage positions, view orders.

Routes delegate to the user's Webull client when Webull credentials exist,
otherwise fall back to the Alpaca-based ExecutionEngine.
"""

import asyncio
import json
from datetime import datetime
from typing import Optional

import structlog
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from sqlalchemy import select

from config.settings import get_settings, TradingMode
from db.database import get_session
from db.models import (
    ApiProvider,
    ApiProviderType,
    PaperPortfolio,
    PaperPosition,
    PaperTrade,
    SystemEventType,
    Trade,
    TradeDirection,
    TradeStatus,
    TradingModeEnum,
    TradingModel,
    UserApiConnection,
    UserApiSettings,
)
from db.encryption import decrypt_value
from risk.manager import RiskManager
from services.event_logger import log_event
from services.indicator_engine import IndicatorEngine
from services.options_data import fetch_options_chain, parse_occ_contract_symbol
from data.market_data import market_data
from news.ingestion import NewsIngestion

# Webull per-user client loader (from our webull routes)
from api.routes.webull import (
    _get_user_clients as _get_user_webull_client,
    invalidate_user_client_cache,
)


def _wb_mode(mode: "TradingModeEnum") -> str:
    """Map TradingModeEnum to Webull SDK mode string."""
    return "real" if mode == TradingModeEnum.LIVE else "paper"

logger = structlog.get_logger(__name__)

router = APIRouter()

_legacy_risk_manager = RiskManager()
_user_risk_managers: dict[int, RiskManager] = {}
_executor = None
_news_ingestion = NewsIngestion()


def _get_legacy_executor():
    """Lazy-init the legacy Alpaca ExecutionEngine for non-user fallback flows."""
    global _executor
    if _executor is None:
        from engine.executor import ExecutionEngine
        _executor = ExecutionEngine(risk_manager=_legacy_risk_manager)
    return _executor


def _get_risk_manager(user_id: int | None) -> RiskManager:
    if user_id is None:
        return _legacy_risk_manager
    return _user_risk_managers.setdefault(user_id, RiskManager())


def _connection_is_live_capable(conn: UserApiConnection, provider: ApiProvider) -> bool:
    if provider.slug == "alpaca":
        return not bool(conn.is_paper if conn.is_paper is not None else True)
    return True


async def _resolve_live_broker_context(user_id: int) -> dict:
    async with get_session() as db:
        settings_result = await db.execute(
            select(UserApiSettings).where(UserApiSettings.user_id == user_id)
        )
        settings = settings_result.scalar_one_or_none()

        result = await db.execute(
            select(UserApiConnection, ApiProvider)
            .join(ApiProvider)
            .where(
                UserApiConnection.user_id == user_id,
                UserApiConnection.status == "connected",
                ApiProvider.api_type == ApiProviderType.BROKERAGE,
            )
        )
        rows = result.all()

    if settings and settings.active_equity_broker_id:
        for conn, provider in rows:
            if conn.id != settings.active_equity_broker_id:
                continue
            if not _connection_is_live_capable(conn, provider):
                return {
                    "connection": None,
                    "provider": None,
                    "reason": "The selected active broker is configured for paper trading only. Choose a live broker in Settings.",
                }
            return {"connection": conn, "provider": provider, "reason": None}

        return {
            "connection": None,
            "provider": None,
            "reason": "The selected active broker is unavailable. Reconnect it or choose a different active broker in Settings.",
        }

    live_capable = [
        (conn, provider)
        for conn, provider in rows
        if _connection_is_live_capable(conn, provider)
    ]
    if len(live_capable) == 1:
        conn, provider = live_capable[0]
        return {"connection": conn, "provider": provider, "reason": None}
    if len(live_capable) > 1:
        return {
            "connection": None,
            "provider": None,
            "reason": "Multiple live brokers are connected. Select an active broker in Settings before trading live.",
        }

    wb = await _get_user_webull_client(user_id, "real")
    if wb:
        return {
            "connection": None,
            "provider": None,
            "legacy_webull": True,
            "reason": None,
        }

    if rows:
        return {
            "connection": None,
            "provider": None,
            "reason": "A connected brokerage was found, but it is not configured for live trading.",
        }

    return {
        "connection": None,
        "provider": None,
        "reason": "No live trading account configured. Connect a live broker in Settings.",
    }


def _get_alpaca_credentials(conn: UserApiConnection) -> tuple[str, str]:
    creds = json.loads(decrypt_value(conn.encrypted_credentials))
    api_key = str(creds.get("api_key", "") or "").strip()
    api_secret = str(creds.get("api_secret", "") or "").strip()
    if not api_key or not api_secret:
        raise HTTPException(status_code=400, detail="Connected Alpaca credentials are incomplete")
    return api_key, api_secret


def _build_alpaca_client(conn: UserApiConnection):
    from alpaca.trading.client import TradingClient

    api_key, api_secret = _get_alpaca_credentials(conn)
    is_paper = bool(conn.is_paper if conn.is_paper is not None else True)
    return TradingClient(api_key=api_key, secret_key=api_secret, paper=is_paper)


async def _fetch_alpaca_account_from_connection(conn: UserApiConnection) -> dict:
    def _fetch() -> dict:
        client = _build_alpaca_client(conn)
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "unrealized_pnl": float(getattr(account, "unrealized_pl", 0) or 0),
            "account_number": getattr(account, "account_number", ""),
            "broker": "alpaca",
        }

    return await asyncio.to_thread(_fetch)


async def _fetch_alpaca_positions(conn: UserApiConnection) -> list[dict]:
    def _fetch() -> list[dict]:
        client = _build_alpaca_client(conn)
        positions = client.get_all_positions()
        return [
            {
                "symbol": position.symbol,
                "quantity": float(position.qty),
                "avg_entry_price": float(position.avg_entry_price),
                "current_price": float(position.current_price),
                "market_value": float(position.market_value),
                "unrealized_pnl": float(position.unrealized_pl),
                "unrealized_pnl_pct": _normalize_unrealized_pnl_pct(float(position.unrealized_plpc)),
                "side": "short" if str(position.side).lower() == "short" else "long",
                "asset_type": "stock",
                "contract_symbol": None,
                "underlying": None,
                "expiration": None,
                "strike": None,
                "option_type": None,
                "avg_premium": None,
                "current_mark": None,
            }
            for position in positions
        ]

    return await asyncio.to_thread(_fetch)


async def _fetch_alpaca_orders(conn: UserApiConnection, status_value: str = "open") -> list[dict]:
    def _fetch() -> list[dict]:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        client = _build_alpaca_client(conn)
        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        request = GetOrdersRequest(status=status_map.get(status_value, QueryOrderStatus.OPEN))
        orders = client.get_orders(request)
        return [
            {
                "id": str(order.id),
                "symbol": order.symbol,
                "direction": str(order.side).lower(),
                "quantity": float(order.qty) if order.qty else 0,
                "order_type": str(order.type).lower(),
                "status": str(order.status).lower(),
                "filled_price": float(order.filled_avg_price) if getattr(order, "filled_avg_price", None) else None,
                "submitted_at": str(order.submitted_at) if getattr(order, "submitted_at", None) else None,
            }
            for order in orders
        ]

    return await asyncio.to_thread(_fetch)


async def _place_alpaca_order(
    conn: UserApiConnection,
    *,
    symbol: str,
    direction: str,
    quantity: float,
    order_type: str,
    limit_price: float | None,
    stop_price: float | None,
) -> dict:
    def _submit() -> dict:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopLimitOrderRequest,
            StopOrderRequest,
        )

        client = _build_alpaca_client(conn)
        normalized_direction = direction.strip().lower()
        side = OrderSide.BUY if normalized_direction in {"long", "buy"} else OrderSide.SELL
        normalized_order_type = order_type.strip().lower()

        if normalized_order_type == "market":
            order_request = MarketOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
        elif normalized_order_type == "limit":
            if limit_price is None:
                raise HTTPException(status_code=400, detail="limit_price is required for limit orders")
            order_request = LimitOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
                limit_price=limit_price,
            )
        elif normalized_order_type == "stop":
            if stop_price is None:
                raise HTTPException(status_code=400, detail="stop_price is required for stop orders")
            order_request = StopOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
                stop_price=stop_price,
            )
        elif normalized_order_type == "stop_limit":
            if stop_price is None or limit_price is None:
                raise HTTPException(status_code=400, detail="stop_price and limit_price are required for stop-limit orders")
            order_request = StopLimitOrderRequest(
                symbol=symbol.upper(),
                qty=quantity,
                side=side,
                time_in_force=TimeInForce.DAY,
                stop_price=stop_price,
                limit_price=limit_price,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported order type: {order_type}")

        try:
            order = client.submit_order(order_request)
        except Exception as exc:
            # Surface Alpaca API errors (insufficient funds, market closed, etc.)
            # as structured responses instead of unhandled 500s
            error_msg = str(exc)
            logger.error(
                "alpaca_order_rejected",
                symbol=symbol,
                direction=direction,
                qty=quantity,
                error=error_msg,
            )
            raise HTTPException(
                status_code=422,
                detail=f"Order rejected by Alpaca: {error_msg}",
            ) from exc
        return {
            "executed": True,
            "mode": "live",
            "success": True,
            "status": str(order.status).lower(),
            "order_id": str(order.id),
            "client_order_id": getattr(order, "client_order_id", None),
        }

    return await asyncio.to_thread(_submit)


async def _persist_legacy_trade_submission(
    user_id: int,
    mode: TradingModeEnum,
    req: "ExecuteSignalRequest",
    order_result: dict,
    current_price: float,
    quantity: float | None = None,
) -> None:
    model_name = (req.model_name or "manual").strip() or "manual"
    direction = req.direction.strip().lower()
    trade_direction = (
        TradeDirection.LONG if direction in ("long", "buy") else TradeDirection.SHORT
    )

    async with get_session() as db:
        result = await db.execute(
            select(TradingModel).where(TradingModel.name == model_name)
        )
        model = result.scalar_one_or_none()
        if model is None:
            model = TradingModel(
                name=model_name,
                model_type="manual",
                mode=mode,
                parameters={},
            )
            db.add(model)
            await db.flush()

        db.add(
            Trade(
                user_id=user_id,
                model_id=model.id,
                symbol=req.symbol.upper(),
                direction=trade_direction,
                quantity=quantity if quantity is not None else req.quantity,
                entry_price=current_price,
                status=TradeStatus.PENDING,
                mode=mode,
                order_id=order_result.get("order_id"),
                notes="broker_order_submission",
            )
        )


def _position_multiplier(symbol: str) -> int:
    return 100 if parse_occ_contract_symbol(symbol) else 1


def _normalize_unrealized_pnl_pct(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    numeric = float(value)
    if abs(numeric) > 2:
        return numeric / 100.0
    return numeric


async def _resolve_reference_price(
    request: Request,
    symbol: str,
    direction: str,
    limit_price: float | None = None,
    stop_price: float | None = None,
) -> float:
    if limit_price and limit_price > 0:
        return limit_price
    if stop_price and stop_price > 0:
        return stop_price

    quote = await get_single_quote(request, symbol=symbol)
    is_buy = direction.strip().lower() in {"long", "buy"}
    price = quote.get("ask") if is_buy else quote.get("bid")
    price = price or quote.get("price") or quote.get("last")
    if not price:
        raise HTTPException(status_code=400, detail=f"Could not price {symbol.upper()}")
    return float(price)


def _paper_trade_sort_key(trade: dict) -> str:
    return trade.get("filled_at") or trade.get("submitted_at") or ""


def _normalize_webull_positions_payload(raw_positions: list[dict]) -> list[dict]:
    positions: list[dict] = []
    for position in raw_positions:
        raw_symbol = position.get("symbol", "")
        contract_meta = parse_occ_contract_symbol(raw_symbol)
        quantity = float(position.get("quantity", 0) or 0)
        avg_entry_price = float(position.get("avg_cost", position.get("cost_price", 0)) or 0)
        current_price = float(position.get("last_price", position.get("market_price", 0)) or 0)
        positions.append({
            "symbol": contract_meta["underlying"] if contract_meta else raw_symbol,
            "quantity": quantity,
            "avg_entry_price": avg_entry_price,
            "current_price": current_price,
            "market_value": float(position.get("market_value", 0) or 0),
            "unrealized_pnl": float(position.get("unrealized_pnl", 0) or 0),
            "unrealized_pnl_pct": _normalize_unrealized_pnl_pct(position.get("unrealized_pnl_pct")),
            "side": "short" if quantity < 0 else "long",
            "asset_type": "option" if contract_meta else "stock",
            "contract_symbol": raw_symbol if contract_meta else None,
            "underlying": contract_meta["underlying"] if contract_meta else None,
            "expiration": contract_meta["expiration"] if contract_meta else None,
            "strike": contract_meta["strike"] if contract_meta else None,
            "option_type": contract_meta["option_type"] if contract_meta else None,
            "avg_premium": avg_entry_price if contract_meta else None,
            "current_mark": current_price if contract_meta else None,
        })
    return positions


def _normalize_webull_orders_payload(raw_orders: list[dict]) -> list[dict]:
    return [
        {
            "id": order.get("client_order_id", order.get("order_id", "")),
            "symbol": order.get("symbol", ""),
            "direction": order.get("side", "").lower(),
            "quantity": order.get("quantity", order.get("total_quantity", 0)),
            "order_type": order.get("order_type", "MKT"),
            "status": order.get("status", "unknown"),
            "filled_price": order.get("filled_price"),
            "submitted_at": order.get("place_time", order.get("created_at", "")),
        }
        for order in raw_orders
    ]


def _extract_bot_explanation(cerberus_trade) -> str | None:
    payload = cerberus_trade.payload_json or {}
    explanation = payload.get("bot_explanation") or payload.get("explanation")
    if isinstance(explanation, str) and explanation.strip():
        return explanation.strip()

    reasons = payload.get("reasons")
    if isinstance(reasons, list):
        joined = "; ".join(str(reason).strip() for reason in reasons if str(reason).strip())
        if joined:
            return joined

    notes = (cerberus_trade.notes or "").strip()
    if notes:
        return notes

    if cerberus_trade.strategy_tag:
        return f"Executed by {cerberus_trade.strategy_tag}"

    return None


def _normalize_paper_trade(paper_trade) -> dict:
    contract_meta = parse_occ_contract_symbol(paper_trade.symbol)
    is_option = contract_meta is not None
    filled_price = paper_trade.exit_price or paper_trade.entry_price
    filled_at = paper_trade.exit_time or paper_trade.entry_time
    direction = "buy" if str(paper_trade.direction).lower().endswith("long") else "sell"
    status_value = paper_trade.status.value if hasattr(paper_trade.status, "value") else str(paper_trade.status)

    if is_option:
        if direction == "buy":
            order_type = "buy_to_open" if status_value == "open" else "buy_to_close"
        else:
            order_type = "sell_to_open" if status_value == "open" else "sell_to_close"
    else:
        order_type = "market"

    normalized = {
        "id": str(paper_trade.id),
        "symbol": contract_meta["underlying"] if contract_meta else paper_trade.symbol,
        "asset_type": "option" if is_option else "stock",
        "direction": direction,
        "quantity": paper_trade.quantity,
        "order_type": order_type,
        "status": "filled",
        "filled_price": filled_price,
        "entry_price": paper_trade.entry_price,
        "limit_price": None,
        "stop_price": None,
        "submitted_at": paper_trade.entry_time.isoformat() if paper_trade.entry_time else None,
        "filled_at": filled_at.isoformat() if filled_at else None,
        "pnl": paper_trade.pnl,
        "total_value": abs(float(paper_trade.quantity or 0)) * float(filled_price or 0) * _position_multiplier(paper_trade.symbol),
        "source": "manual",
        "bot_name": None,
        "bot_explanation": None,
    }

    if contract_meta:
        normalized.update(
            {
                "contract_symbol": paper_trade.symbol,
                "underlying": contract_meta["underlying"],
                "expiration": contract_meta["expiration"],
                "strike": contract_meta["strike"],
                "option_type": contract_meta["option_type"],
            }
        )

    return normalized


def _normalize_cerberus_trade(cerberus_trade) -> dict:
    payload = cerberus_trade.payload_json or {}
    filled_price = cerberus_trade.exit_price or cerberus_trade.entry_price
    filled_at = cerberus_trade.exit_ts or cerberus_trade.entry_ts or cerberus_trade.created_at
    direction = (cerberus_trade.side or "buy").lower()
    return {
        "id": str(cerberus_trade.id),
        "symbol": cerberus_trade.symbol,
        "asset_type": cerberus_trade.asset_type or "stock",
        "direction": direction,
        "quantity": cerberus_trade.quantity,
        "order_type": payload.get("order_type") or "market",
        "status": "filled",
        "filled_price": filled_price,
        "entry_price": cerberus_trade.entry_price,
        "limit_price": payload.get("limit_price"),
        "stop_price": payload.get("stop_price"),
        "submitted_at": (cerberus_trade.entry_ts or cerberus_trade.created_at).isoformat() if (cerberus_trade.entry_ts or cerberus_trade.created_at) else None,
        "filled_at": filled_at.isoformat() if filled_at else None,
        "pnl": cerberus_trade.net_pnl if cerberus_trade.net_pnl is not None else cerberus_trade.gross_pnl,
        "total_value": abs(float(cerberus_trade.quantity or 0)) * float(filled_price or 0) * _position_multiplier(cerberus_trade.symbol),
        "source": "bot" if cerberus_trade.bot_id or cerberus_trade.strategy_tag else "manual",
        "bot_name": cerberus_trade.strategy_tag,
        "bot_explanation": _extract_bot_explanation(cerberus_trade),
    }


def _dict_or_none(value) -> dict:
    return value if isinstance(value, dict) else {}


def _read_value(source, *keys):
    if source is None:
        return None
    if isinstance(source, dict):
        for key in keys:
            if key in source and source[key] is not None:
                return source[key]
        return None

    for key in keys:
        value = getattr(source, key, None)
        if value is not None:
            return value
    return None


def _normalize_percent(value) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if abs(numeric) <= 1:
        return round(numeric * 100, 4)
    return round(numeric, 4)


def _normalize_iso_timestamp(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if value > 10_000_000_000:
            value = value / 1000.0
        return datetime.utcfromtimestamp(value).isoformat() + "Z"
    if isinstance(value, str):
        return value
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return None


async def _fetch_symbol_snapshot_payload(symbol: str) -> dict:
    import yfinance as yf

    def _fetch() -> dict:
        ticker = yf.Ticker(symbol.upper())
        fast_info = _dict_or_none(getattr(ticker, "fast_info", None))
        info = _dict_or_none(getattr(ticker, "info", None))

        name = info.get("shortName") or info.get("longName") or symbol.upper()
        exchange = info.get("fullExchangeName") or info.get("exchange")
        price = (
            _read_value(fast_info, "lastPrice", "last_price")
            or info.get("currentPrice")
            or info.get("regularMarketPrice")
            or info.get("ask")
            or 0
        )
        prev_close = (
            _read_value(fast_info, "previousClose", "previous_close")
            or info.get("regularMarketPreviousClose")
            or info.get("previousClose")
            or price
        )
        change = float(price or 0) - float(prev_close or 0)
        change_pct = (change / float(prev_close)) * 100 if prev_close else 0.0
        dividend_yield = info.get("dividendYield")
        if dividend_yield is not None and abs(float(dividend_yield)) <= 1:
            dividend_yield = float(dividend_yield) * 100

        return {
            "symbol": symbol.upper(),
            "name": name,
            "exchange": exchange,
            "price": round(float(price or 0), 4),
            "bid": _read_value(fast_info, "bid") or info.get("bid"),
            "ask": _read_value(fast_info, "ask") or info.get("ask"),
            "last": round(float(price or 0), 4),
            "change": round(float(change), 4),
            "change_pct": round(float(change_pct), 4),
            "volume": int(
                float(
                    _read_value(fast_info, "lastVolume", "last_volume")
                    or info.get("regularMarketVolume")
                    or info.get("volume")
                    or 0
                )
            ),
            "high": _read_value(fast_info, "dayHigh", "day_high") or info.get("dayHigh"),
            "low": _read_value(fast_info, "dayLow", "day_low") or info.get("dayLow"),
            "open": info.get("open"),
            "prev_close": round(float(prev_close or 0), 4),
            "market_cap": _read_value(fast_info, "marketCap", "market_cap") or info.get("marketCap"),
            "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
            "week52_high": _read_value(fast_info, "yearHigh", "fiftyTwoWeekHigh")
            or info.get("fiftyTwoWeekHigh"),
            "week52_low": _read_value(fast_info, "yearLow", "fiftyTwoWeekLow")
            or info.get("fiftyTwoWeekLow"),
            "dividend_yield": round(float(dividend_yield), 4) if dividend_yield is not None else None,
            "average_volume": _read_value(
                fast_info,
                "threeMonthAverageVolume",
                "tenDayAverageVolume",
                "three_month_average_volume",
            )
            or info.get("averageVolume"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "company_summary": info.get("longBusinessSummary"),
            "currency": info.get("currency") or "USD",
            "market_status": info.get("marketState"),
            "source": "yfinance",
        }

    return await asyncio.to_thread(_fetch)


async def _fetch_snapshot_details(symbol: str) -> dict:
    try:
        import yfinance as yf

        def _load() -> dict:
            ticker = yf.Ticker(symbol.upper())
            fast_info = ticker.fast_info or {}
            info = ticker.info or {}
            return {
                "name": info.get("shortName") or info.get("longName"),
                "exchange": info.get("fullExchangeName") or info.get("exchange"),
                "market_cap": fast_info.get("market_cap") or info.get("marketCap"),
                "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
                "fifty_two_week_low": fast_info.get("year_low") or info.get("fiftyTwoWeekLow"),
                "fifty_two_week_high": fast_info.get("year_high") or info.get("fiftyTwoWeekHigh"),
                "dividend_yield": info.get("dividendYield"),
                "avg_volume": fast_info.get("three_month_average_volume")
                or info.get("averageVolume"),
                "currency": info.get("currency") or "USD",
                "market_state": info.get("marketState") or fast_info.get("market_state"),
            }

        return await asyncio.to_thread(_load)
    except Exception as exc:
        logger.warning("symbol_snapshot_details_failed", symbol=symbol, error=str(exc))
        return {}


def _connected_status(message: str, source: str | None = None) -> dict:
    return {
        "status": "connected",
        "message": message,
        "source": source,
    }


def _warning_status(message: str, source: str | None = None) -> dict:
    return {
        "status": "warning",
        "message": message,
        "source": source,
    }


def _disconnected_status(message: str, source: str | None = None) -> dict:
    return {
        "status": "disconnected",
        "message": message,
        "source": source,
    }

class ExecuteSignalRequest(BaseModel):
    symbol: str
    direction: str  # "long", "short", "flat" or "BUY", "SELL"
    strength: float = 1.0
    quantity: float = 10.0
    dollar_amount: Optional[float] = None
    model_name: str = "manual"
    order_type: str = "market"
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    user_confirmed: bool = False


class SwitchModeRequest(BaseModel):
    mode: str  # "paper", "live", "backtest"


class ExecuteOptionRequest(BaseModel):
    contract_symbol: Optional[str] = None
    underlying: str
    expiration: str
    strike: float
    option_type: str
    direction: str
    quantity: int = 1
    user_confirmed: bool = False


# ── Core trading routes (Webull-aware) ───────────────────────────────────


@router.get("/account")
async def get_account(request: Request):
    """Get current account information — routes by active trading mode.

    Live mode requires a user-owned active broker selection.
    Paper and backtest modes always use the local paper portfolio.
    """
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        broker_context = await _resolve_live_broker_context(user_id)
        provider = broker_context.get("provider")
        connection = broker_context.get("connection")

        if provider and provider.slug == "webull":
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                summary = await asyncio.to_thread(wb.account.get_summary)
                if summary:
                    return {
                        "equity": summary.get("net_liquidation", 0),
                        "cash": summary.get("cash_balance", 0),
                        "buying_power": summary.get("buying_power", 0),
                        "portfolio_value": summary.get("total_market_value", 0),
                        "unrealized_pnl": summary.get("unrealized_pnl", 0),
                        "realized_pnl": summary.get("realized_pnl", 0),
                        "account_id": summary.get("account_id"),
                        "mode": mode.value.upper(),
                        "broker": "webull",
                    }
                invalidate_user_client_cache(user_id, "real")
                logger.warning("webull_account_fetch_failed_evicting_cache", user_id=user_id, mode=mode.value)

        if provider and provider.slug == "alpaca" and connection:
            try:
                alpaca_account = await _fetch_alpaca_account_from_connection(connection)
                return {**alpaca_account, "mode": mode.value.upper()}
            except HTTPException:
                raise
            except Exception as exc:
                logger.warning("alpaca_account_fetch_failed", user_id=user_id, connection_id=connection.id, error=str(exc))

        if broker_context.get("legacy_webull"):
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                summary = await asyncio.to_thread(wb.account.get_summary)
                if summary:
                    return {
                        "equity": summary.get("net_liquidation", 0),
                        "cash": summary.get("cash_balance", 0),
                        "buying_power": summary.get("buying_power", 0),
                        "portfolio_value": summary.get("total_market_value", 0),
                        "unrealized_pnl": summary.get("unrealized_pnl", 0),
                        "realized_pnl": summary.get("realized_pnl", 0),
                        "account_id": summary.get("account_id"),
                        "mode": mode.value.upper(),
                        "broker": "webull",
                    }

        return {
            "equity": 0,
            "cash": 0,
            "buying_power": 0,
            "portfolio_value": 0,
            "broker": "none",
            "mode": "LIVE",
            "not_configured": True,
            "message": broker_context.get("reason") or "No live trading account configured. Connect a live broker in Settings.",
        }

    if user_id:
        async with get_session() as session:
            result = await session.execute(
                select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
            )
            portfolio = result.scalar_one_or_none()

            if not portfolio:
                portfolio = PaperPortfolio(
                    user_id=user_id,
                    cash=1_000_000.0,
                    initial_capital=1_000_000.0,
                )
                session.add(portfolio)
                await session.flush()

            # Sum positions value
            pos_result = await session.execute(
                select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
            )
            positions = pos_result.scalars().all()
            positions_value = sum(
                (p.current_price or p.avg_entry_price) * p.quantity * _position_multiplier(p.symbol)
                for p in positions
            )

            return {
                "equity": portfolio.cash + positions_value,
                "cash": portfolio.cash,
                "buying_power": portfolio.cash,
                "portfolio_value": positions_value,
                "broker": "paper",
                "mode": mode.value.upper(),
            }

    try:
        return _get_legacy_executor().get_account()
    except Exception as exc:
        logger.warning("get_account_failed", user_id=user_id, mode=mode.value, error=str(exc))
        raise HTTPException(status_code=503, detail="No broker connected")


@router.get("/positions")
async def get_positions(request: Request):
    """Get all open positions — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        broker_context = await _resolve_live_broker_context(user_id)
        provider = broker_context.get("provider")
        connection = broker_context.get("connection")

        if provider and provider.slug == "webull":
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                raw = await asyncio.to_thread(wb.account.get_positions)
                return {"positions": _normalize_webull_positions_payload(raw), "mode": mode.value}

        if provider and provider.slug == "alpaca" and connection:
            positions = await _fetch_alpaca_positions(connection)
            return {"positions": positions, "mode": mode.value}

        if broker_context.get("legacy_webull"):
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                raw = await asyncio.to_thread(wb.account.get_positions)
                return {"positions": _normalize_webull_positions_payload(raw), "mode": mode.value}

        reason = broker_context.get("reason") or "No live broker configured"
        return {"positions": [], "mode": mode.value, "not_configured": True, "message": reason}

    if user_id:
        from api.routes.paper_trading import get_paper_positions
        result = await get_paper_positions(request)
        if isinstance(result, dict):
            result["mode"] = mode.value
        return result

    try:
        return _get_legacy_executor().get_positions()
    except Exception as exc:
        logger.warning("get_positions_failed", user_id=user_id, mode=mode.value, error=str(exc))
        raise HTTPException(status_code=503, detail="No broker connected")


@router.get("/orders")
async def get_orders(request: Request, status: str = "open"):
    """Get orders — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode == TradingModeEnum.LIVE:
        broker_context = await _resolve_live_broker_context(user_id)
        provider = broker_context.get("provider")
        connection = broker_context.get("connection")

        if provider and provider.slug == "webull":
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                raw = await asyncio.to_thread(wb.account.get_open_orders)
                return {"orders": _normalize_webull_orders_payload(raw), "mode": mode.value}

        if provider and provider.slug == "alpaca" and connection:
            orders = await _fetch_alpaca_orders(connection, status)
            return {"orders": orders, "mode": mode.value}

        if broker_context.get("legacy_webull"):
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                raw = await asyncio.to_thread(wb.account.get_open_orders)
                return {"orders": _normalize_webull_orders_payload(raw), "mode": mode.value}

        reason = broker_context.get("reason") or "No live broker configured"
        return {"orders": [], "mode": mode.value, "not_configured": True, "message": reason}

    if user_id and mode in (TradingModeEnum.PAPER, TradingModeEnum.BACKTEST):
        return {"orders": [], "mode": "paper"}

    try:
        return _get_legacy_executor().get_orders(status=status)
    except Exception as e:
        logger.warning("get_orders_failed", error=str(e))
        return {"orders": []}


@router.get("/quotes")
async def get_quotes(
    request: Request,
    symbols: str = Query(default="SPY,QQQ,AAPL,TSLA,NVDA,MSFT"),
):
    """Get stock quotes — uses Webull if connected, fallback to unofficial SDK."""
    symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
    user_id = getattr(request.state, "user_id", None)

    quotes: list[dict] = []
    resolved_symbols: set[str] = set()

    # 1. Try Webull SDK (per-user, authenticated) for all symbols
    if user_id:
        mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
        wb = await _get_user_webull_client(user_id, _wb_mode(mode))
        if wb:
            try:
                raw = await asyncio.to_thread(wb.market_data.get_quotes, symbol_list)
                for sym in symbol_list:
                    q = raw.get(sym, {})
                    if q:
                        quotes.append({
                            "symbol": sym,
                            "price": q.get("price", q.get("close", 0)),
                            "change": q.get("change", 0),
                            "change_pct": q.get("change_pct", 0),
                            "volume": q.get("volume", 0),
                            "high": q.get("high", 0),
                            "low": q.get("low", 0),
                            "open": q.get("open", 0),
                            "prev_close": q.get("prev_close", 0),
                        })
                        resolved_symbols.add(sym)
            except Exception as e:
                logger.warning("webull_quotes_failed", error=str(e))

    # 2. Fall back for any symbols not resolved by Webull
    missing = [s for s in symbol_list if s not in resolved_symbols]
    if missing:
        try:
            import yfinance as yf
            for sym in missing:
                try:
                    ticker = yf.Ticker(sym)
                    fast_info = getattr(ticker, "fast_info", None)
                    info = getattr(ticker, "info", None) or {}
                    fi = dict(fast_info) if fast_info else {}
                    price = (
                        fi.get("lastPrice", fi.get("last_price"))
                        or info.get("currentPrice")
                        or info.get("regularMarketPrice")
                        or 0
                    )
                    prev_close = (
                        fi.get("previousClose", fi.get("previous_close"))
                        or info.get("regularMarketPreviousClose")
                        or price
                    )
                    change = float(price or 0) - float(prev_close or 0)
                    change_pct = (change / float(prev_close)) * 100 if prev_close else 0.0
                    volume = int(float(
                        fi.get("lastVolume", fi.get("last_volume"))
                        or info.get("regularMarketVolume")
                        or info.get("volume")
                        or 0
                    ))
                    quotes.append({
                        "symbol": sym,
                        "price": round(float(price or 0), 4),
                        "change": round(float(change), 4),
                        "change_pct": round(float(change_pct), 4),
                        "volume": volume,
                        "high": float(fi.get("dayHigh", fi.get("day_high")) or info.get("dayHigh") or 0),
                        "low": float(fi.get("dayLow", fi.get("day_low")) or info.get("dayLow") or 0),
                        "open": float(info.get("open") or 0),
                        "prev_close": round(float(prev_close or 0), 4),
                    })
                    resolved_symbols.add(sym)
                except Exception as e:
                    logger.warning("yfinance_quote_failed", symbol=sym, error=str(e))
        except ImportError:
            logger.warning("yfinance_not_available")

    # 3. Last resort: unofficial webull SDK for still-missing symbols
    still_missing = [s for s in symbol_list if s not in resolved_symbols]
    if still_missing:
        try:
            from webull import webull as WebullUnofficial
            uwb = WebullUnofficial()
            for sym in still_missing:
                raw = uwb.get_quote(sym)
                if raw:
                    quotes.append({
                        "symbol": sym,
                        "price": float(raw.get("close", 0)),
                        "change": float(raw.get("change", 0)),
                        "change_pct": float(raw.get("changeRatio", 0)) * 100,
                        "volume": int(float(raw.get("volume", 0))),
                        "high": float(raw.get("high", 0)),
                        "low": float(raw.get("low", 0)),
                        "open": float(raw.get("open", 0)),
                        "prev_close": float(raw.get("preClose", 0)),
                    })
        except Exception as e:
            logger.warning("quote_fallback_failed", error=str(e))

    return {"quotes": quotes}


@router.get("/quote")
async def get_single_quote(request: Request, symbol: str = Query(...)):
    """Get a single stock quote (used by the order form)."""
    try:
        return await _fetch_symbol_snapshot_payload(symbol)
    except Exception as exc:
        logger.warning("single_quote_snapshot_failed", symbol=symbol, error=str(exc))
        result = await get_quotes(request, symbols=symbol)
        quotes = result.get("quotes", [])
        if quotes:
            return quotes[0]
        return {"symbol": symbol.upper(), "price": 0}


@router.get("/snapshot")
async def get_symbol_snapshot(request: Request, symbol: str = Query(...)):
    quote = await get_single_quote(request, symbol=symbol)
    return {
        "symbol": symbol.upper(),
        "name": quote.get("name"),
        "exchange": quote.get("exchange"),
        "price": float(quote.get("price") or quote.get("last") or 0),
        "bid": quote.get("bid"),
        "ask": quote.get("ask"),
        "last": quote.get("last") or quote.get("price"),
        "change": quote.get("change"),
        "change_pct": quote.get("change_pct"),
        "volume": quote.get("volume"),
        "market_cap": quote.get("market_cap"),
        "pe_ratio": quote.get("pe_ratio"),
        "fifty_two_week_low": quote.get("week52_low"),
        "fifty_two_week_high": quote.get("week52_high"),
        "dividend_yield": quote.get("dividend_yield"),
        "avg_volume": quote.get("average_volume"),
        "market_state": quote.get("market_status"),
        "currency": quote.get("currency") or "USD",
        "source": quote.get("source"),
        "sector": quote.get("sector"),
        "industry": quote.get("industry"),
        "description": quote.get("company_summary"),
    }


@router.get("/news")
async def get_symbol_news(symbol: str = Query(...), limit: int = Query(6, ge=1, le=20)):
    articles = await asyncio.to_thread(_news_ingestion.fetch_news, [symbol.upper()], limit)
    normalized = [
        {
            "title": article.get("title", ""),
            "url": article.get("url", ""),
            "source": article.get("source", ""),
            "published_at": article.get("published_at"),
            "summary": article.get("summary", ""),
            "symbols": article.get("symbols", []),
        }
        for article in articles
    ]
    return {"symbol": symbol.upper(), "articles": normalized}


@router.get("/status")
async def get_trading_status(request: Request, symbol: str = Query("SPY")):
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
    account = await get_account(request)
    quote = await market_data.get_quote(symbol.upper())

    if quote and float(quote.get("price") or 0) > 0:
        market_status = _connected_status(
            f"Streaming {symbol.upper()} pricing is available",
            quote.get("source"),
        )
    else:
        market_status = _disconnected_status(
            f"Could not refresh {symbol.upper()} market data",
            None,
        )

    broker = account.get("broker")
    if mode == TradingModeEnum.LIVE:
        if account.get("not_configured") or broker in {None, "none"}:
            order_status = _disconnected_status(
                "Live order routing is not configured",
                broker,
            )
        else:
            order_status = _warning_status(
                f"Orders will route to {broker}",
                broker,
            )
    elif broker in {"paper", "webull", "alpaca"}:
        order_status = _connected_status(
            f"Orders are staged through {broker}",
            broker,
        )
    else:
        order_status = _warning_status(
            "Paper routing is available but no external broker is attached",
            broker,
        )

    return {
        "mode": mode.value,
        "broker": broker,
        "market_data": market_status,
        "order_routing": order_status,
    }


@router.get("/execute")
async def execute_signal_get():
    """Return a helpful 405 when someone hits /execute with GET."""
    from fastapi.responses import JSONResponse

    return JSONResponse(
        status_code=405,
        content={
            "error": "Use POST to submit trade orders",
            "method": "POST",
            "required_fields": ["symbol", "side", "quantity"],
        },
    )


@router.post("/execute")
async def execute_signal(request: Request, req: ExecuteSignalRequest):
    """Execute a trade — routes by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
    resolved_quantity = req.quantity

    if req.dollar_amount is not None:
        reference_price = await _resolve_reference_price(
            request,
            req.symbol,
            req.direction,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )
        resolved_quantity = int(req.dollar_amount / reference_price)
        if resolved_quantity < 1:
            raise HTTPException(
                status_code=400,
                detail=f"Dollar amount ${req.dollar_amount:,.2f} is too small for one share of {req.symbol.upper()}",
            )

    if user_id and mode == TradingModeEnum.LIVE:
        broker_context = await _resolve_live_broker_context(user_id)
        provider = broker_context.get("provider")
        connection = broker_context.get("connection")

        if provider and provider.slug == "webull":
            wb = await _get_user_webull_client(user_id, "real")
            if not wb:
                raise HTTPException(status_code=503, detail="Active Webull broker is unavailable")

            from data.webull.trading import OrderRequest as WBOrderRequest
            # Map direction to Webull side
            side = req.direction.upper()
            if side in ("LONG", "BUY"):
                side = "BUY"
            elif side in ("SHORT", "SELL", "FLAT"):
                side = "SELL"

            order_type_map = {
                "market": "MKT",
                "limit": "LMT",
                "stop": "STP",
                "stop_limit": "STP_LMT",
            }
            order_type = order_type_map.get(req.order_type.lower(), "MKT")

            wb_req = WBOrderRequest(
                symbol=req.symbol.upper(),
                side=side,
                qty=int(resolved_quantity),
                order_type=order_type,
                limit_price=req.limit_price,
                stop_price=req.stop_price,
            )
            order_result = await asyncio.to_thread(
                wb.trading.place_order,
                wb_req,
                user_confirmed=req.user_confirmed,
            )

            if not order_result.success and not order_result.order_id:
                if "confirm" in (order_result.error or "").lower():
                    return {
                        "executed": False,
                        "blocked": True,
                        "reason": order_result.error or "Order requires user_confirmed=true",
                        "mode": "live",
                    }
                await log_event(
                    user_id=user_id,
                    event_type=SystemEventType.TRADE_FAILED,
                    mode=TradingModeEnum.LIVE,
                    description=f"LIVE order failed: {order_result.error or 'unknown'}",
                )
                raise HTTPException(status_code=400, detail=order_result.error or "Order failed")

            # Success
            await log_event(
                user_id=user_id,
                event_type=SystemEventType.TRADE_EXECUTED,
                mode=TradingModeEnum.LIVE,
                description=f"LIVE {side} {int(resolved_quantity)} {req.symbol.upper()}",
            )
            return {
                "executed": True,
                "mode": "live",
                "success": True,
                "status": "pending",
                "order_id": order_result.order_id,
                "client_order_id": order_result.client_order_id,
                "resolved_quantity": resolved_quantity,
            }

        if provider and provider.slug == "alpaca" and connection:
            from models.base import Signal

            signal = Signal(
                symbol=req.symbol,
                direction=req.direction,
                strength=req.strength,
                model_name=req.model_name,
            )
            risk_manager = _get_risk_manager(user_id)
            account = await _fetch_alpaca_account_from_connection(connection)
            positions = await _fetch_alpaca_positions(connection)
            current_exposure = sum(abs(float(position.get("market_value") or 0)) for position in positions)
            current_price = await _resolve_reference_price(
                request,
                req.symbol,
                req.direction,
                limit_price=req.limit_price,
                stop_price=req.stop_price,
            )
            approved, adjusted_quantity, reason = risk_manager.validate_trade(
                signal=signal,
                proposed_size=resolved_quantity,
                current_equity=float(account["equity"]),
                current_exposure=current_exposure,
                current_price=current_price,
            )
            if not approved:
                raise HTTPException(status_code=422, detail=reason)

            order_result = await _place_alpaca_order(
                connection,
                symbol=req.symbol,
                direction=req.direction,
                quantity=adjusted_quantity,
                order_type=req.order_type,
                limit_price=req.limit_price,
                stop_price=req.stop_price,
            )
            risk_manager.register_position(req.symbol.upper(), current_price, adjusted_quantity, req.direction.strip().lower())
            await log_event(
                user_id=user_id,
                event_type=SystemEventType.TRADE_EXECUTED,
                mode=TradingModeEnum.LIVE,
                description=f"LIVE {req.direction.upper()} {float(adjusted_quantity):g} {req.symbol.upper()} via Alpaca",
            )
            try:
                await _persist_legacy_trade_submission(
                    user_id=user_id,
                    mode=TradingModeEnum.LIVE,
                    req=req,
                    order_result=order_result,
                    current_price=current_price,
                    quantity=adjusted_quantity,
                )
            except Exception as exc:
                logger.error(
                    "alpaca_trade_persist_failed",
                    user_id=user_id,
                    symbol=req.symbol.upper(),
                    direction=req.direction,
                    quantity=adjusted_quantity,
                    order_id=order_result.get("order_id", "unknown"),
                    error=str(exc),
                    hint="Order executed in broker but NOT saved to database — reconciliation needed",
                )
            order_result["resolved_quantity"] = adjusted_quantity
            return order_result

        if broker_context.get("legacy_webull"):
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                from data.webull.trading import OrderRequest as WBOrderRequest

                side = req.direction.upper()
                if side in ("LONG", "BUY"):
                    side = "BUY"
                elif side in ("SHORT", "SELL", "FLAT"):
                    side = "SELL"

                order_type_map = {
                    "market": "MKT",
                    "limit": "LMT",
                    "stop": "STP",
                    "stop_limit": "STP_LMT",
                }
                wb_req = WBOrderRequest(
                    symbol=req.symbol.upper(),
                    side=side,
                    qty=int(resolved_quantity),
                    order_type=order_type_map.get(req.order_type.lower(), "MKT"),
                    limit_price=req.limit_price,
                    stop_price=req.stop_price,
                )
                order_result = await asyncio.to_thread(
                    wb.trading.place_order,
                    wb_req,
                    user_confirmed=req.user_confirmed,
                )
                if not order_result.success and not order_result.order_id:
                    raise HTTPException(status_code=400, detail=order_result.error or "Order failed")
                return {
                    "executed": True,
                    "mode": "live",
                    "success": True,
                    "status": "pending",
                    "order_id": order_result.order_id,
                    "client_order_id": order_result.client_order_id,
                    "resolved_quantity": resolved_quantity,
                }

        raise HTTPException(status_code=400, detail=broker_context.get("reason") or "No live broker is configured")

    # Paper mode — route through paper trading for authenticated users
    if user_id and mode in (TradingModeEnum.PAPER, TradingModeEnum.BACKTEST):
        from api.routes.paper_trading import PaperTradeRequest, execute_paper_trade

        side = req.direction.upper()
        if side in ("LONG", "BUY"):
            side = "BUY"
        elif side in ("SHORT", "SELL", "FLAT"):
            side = "SELL"

        paper_req = PaperTradeRequest(
            symbol=req.symbol,
            side=side,
            quantity=resolved_quantity,
            notional=req.dollar_amount,
            user_confirmed=req.user_confirmed,
        )
        result = await execute_paper_trade(request, paper_req)
        actual_quantity = (
            float(result.get("quantity"))
            if isinstance(result, dict) and result.get("quantity") is not None
            else resolved_quantity
        )

        await log_event(
            user_id=user_id,
            event_type=SystemEventType.TRADE_EXECUTED,
            mode=mode,
            description=f"PAPER {side} {int(actual_quantity)} {req.symbol.upper()}",
        )

        if isinstance(result, dict):
            result["mode"] = mode.value
            result["resolved_quantity"] = actual_quantity
            result.setdefault("status", "filled")
        return result

    # Last resort: Alpaca executor (no user context)
    from models.base import Signal
    from engine.executor import OrderType

    signal = Signal(
        symbol=req.symbol,
        direction=req.direction,
        strength=req.strength,
        model_name=req.model_name,
    )

    try:
        account = _get_legacy_executor().get_account()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Broker unavailable: {str(e)}")

    current_equity = account["equity"]
    positions = _get_legacy_executor().get_positions()
    current_exposure = sum(abs(float(p["market_value"])) for p in positions)

    current_price = req.limit_price or req.stop_price or 0
    if current_price == 0 and req.dollar_amount is not None:
        current_price = await _resolve_reference_price(
            request,
            req.symbol,
            req.direction,
            limit_price=req.limit_price,
            stop_price=req.stop_price,
        )
    if current_price == 0:
        raise HTTPException(status_code=400, detail="Price required for execution")

    result = _get_legacy_executor().execute_signal(
        signal=signal,
        quantity=resolved_quantity,
        current_price=current_price,
        current_equity=current_equity,
        current_exposure=current_exposure,
        order_type=OrderType(req.order_type),
        limit_price=req.limit_price,
    )

    if result is None:
        raise HTTPException(status_code=422, detail="Trade rejected by risk management")

    if user_id and req.direction.strip().lower() != "flat":
        try:
            await _persist_legacy_trade_submission(
                user_id=user_id,
                mode=mode,
                req=req,
                order_result=result,
                current_price=current_price,
            )
        except Exception as exc:
            logger.warning(
                "legacy_trade_persist_failed",
                user_id=user_id,
                symbol=req.symbol.upper(),
                error=str(exc),
            )

    return result


@router.get("/options-chain")
async def get_options_chain_data(
    symbol: str = Query(...),
    expiration: Optional[str] = Query(default=None),
):
    """Get normalized options chain data via market-data fallback."""
    chain = await fetch_options_chain(symbol, expiration=expiration)
    return {
        "symbol": chain.get("symbol", symbol.upper()),
        "expirations": chain.get("expirations", []),
        "selected_expiration": chain.get("selected_expiration"),
        "contracts": chain.get("contracts", []),
        "strikes": chain.get("strikes", []),
    }


@router.post("/execute-option")
async def execute_option(request: Request, req: ExecuteOptionRequest):
    """Execute a paper options trade using normalized contract metadata."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if user_id and mode in (TradingModeEnum.PAPER, TradingModeEnum.BACKTEST):
        from api.routes.paper_trading import PaperTradeRequest, execute_paper_trade

        direction = req.direction.lower()
        if direction in ("buy_to_open", "buy_to_close"):
            side = "BUY"
        elif direction in ("sell_to_open", "sell_to_close"):
            side = "SELL"
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported option direction: {req.direction}")

        paper_req = PaperTradeRequest(
            symbol=req.underlying,
            side=side,
            quantity=req.quantity,
            user_confirmed=req.user_confirmed,
            instrument_type="option",
            contract_symbol=req.contract_symbol,
            option_type=req.option_type,
            strike=req.strike,
            expiry=req.expiration,
        )
        result = await execute_paper_trade(request, paper_req)

        await log_event(
            user_id=user_id,
            event_type=SystemEventType.TRADE_EXECUTED,
            mode=mode,
            description=f"PAPER OPTION {direction.upper()} {req.quantity} {req.underlying.upper()} {req.expiration} {req.strike}{req.option_type[:1].upper()}",
        )

        if isinstance(result, dict):
            result.update(
                {
                    "mode": mode.value,
                    "underlying": req.underlying.upper(),
                    "expiration": req.expiration,
                    "strike": req.strike,
                    "option_type": req.option_type,
                    "direction": direction,
                }
            )
        return result

    raise HTTPException(
        status_code=422,
        detail="Options execution is currently supported in paper mode only",
    )


# ── Risk & utility routes ────────────────────────────────────────────────


@router.get("/risk-summary")
async def get_risk_summary(request: Request):
    """Get current risk status — scoped to active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)
    settings = get_settings()

    if user_id and mode == TradingModeEnum.LIVE:
        broker_context = await _resolve_live_broker_context(user_id)
        provider = broker_context.get("provider")
        connection = broker_context.get("connection")
        if provider and provider.slug == "webull":
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                summary = await asyncio.to_thread(wb.account.get_summary)
                equity = summary.get("net_liquidation", 0) if summary else 0
                return {
                    "is_halted": False,
                    "halt_reason": None,
                    "current_drawdown_pct": 0.0,
                    "max_drawdown_limit": settings.max_drawdown_pct,
                    "max_drawdown_limit_pct": settings.max_drawdown_pct,
                    "current_exposure_pct": 0.0,
                    "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
                    "trades_last_hour": 0,
                    "trades_this_hour": 0,
                    "max_trades_per_hour": settings.max_trades_per_hour,
                    "peak_equity": equity,
                    "open_positions": 0,
                    "recent_risk_events": 0,
                    "equity": equity,
                    "mode": "live",
                }
        if provider and provider.slug == "alpaca" and connection:
            account = await _fetch_alpaca_account_from_connection(connection)
            summary = _get_risk_manager(user_id).get_risk_summary(float(account["equity"]))
            summary["equity"] = float(account["equity"])
            summary["mode"] = "live"
            return summary
        if broker_context.get("legacy_webull"):
            wb = await _get_user_webull_client(user_id, "real")
            if wb:
                summary = await asyncio.to_thread(wb.account.get_summary)
                equity = summary.get("net_liquidation", 0) if summary else 0
                return {
                    "is_halted": False,
                    "halt_reason": None,
                    "current_drawdown_pct": 0.0,
                    "max_drawdown_limit": settings.max_drawdown_pct,
                    "max_drawdown_limit_pct": settings.max_drawdown_pct,
                    "current_exposure_pct": 0.0,
                    "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
                    "trades_last_hour": 0,
                    "trades_this_hour": 0,
                    "max_trades_per_hour": settings.max_trades_per_hour,
                    "peak_equity": equity,
                    "open_positions": 0,
                    "recent_risk_events": 0,
                    "equity": equity,
                    "mode": "live",
                }
        return {
            "is_halted": False,
            "halt_reason": None,
            "current_drawdown_pct": 0.0,
            "max_drawdown_limit": settings.max_drawdown_pct,
            "max_drawdown_limit_pct": settings.max_drawdown_pct,
            "current_exposure_pct": 0.0,
            "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
            "trades_last_hour": 0,
            "trades_this_hour": 0,
            "max_trades_per_hour": settings.max_trades_per_hour,
            "peak_equity": 0,
            "open_positions": 0,
            "recent_risk_events": 0,
            "mode": "live",
        }

    if user_id:
        return {
            "is_halted": False,
            "halt_reason": None,
            "current_drawdown_pct": 0.0,
            "max_drawdown_limit": settings.max_drawdown_pct,
            "max_drawdown_limit_pct": settings.max_drawdown_pct,
            "current_exposure_pct": 0.0,
            "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
            "trades_last_hour": 0,
            "trades_this_hour": 0,
            "max_trades_per_hour": settings.max_trades_per_hour,
            "peak_equity": 0,
            "open_positions": 0,
            "recent_risk_events": 0,
            "mode": mode.value,
        }
    try:
        account = _get_legacy_executor().get_account()
        summary = _legacy_risk_manager.get_risk_summary(account["equity"])
        summary["mode"] = mode.value
        return summary
    except Exception as exc:
        logger.warning("risk_summary_fetch_failed", mode=mode.value, error=str(exc))
        return {
            "is_halted": True,
            "halt_reason": "Risk data unavailable — halting as precaution",
            "current_drawdown_pct": 0.0,
            "max_drawdown_limit": settings.max_drawdown_pct,
            "max_drawdown_limit_pct": settings.max_drawdown_pct,
            "current_exposure_pct": 0.0,
            "max_exposure_limit_pct": settings.max_portfolio_exposure_pct,
            "trades_last_hour": 0,
            "trades_this_hour": 0,
            "max_trades_per_hour": settings.max_trades_per_hour,
            "peak_equity": 0,
            "open_positions": 0,
            "recent_risk_events": 0,
            "mode": mode.value,
            "data_unavailable": True,
        }


@router.get("/trade-log")
async def get_trade_log(request: Request, limit: int = Query(default=100, ge=1, le=500)):
    """Get execution audit trail — filtered by active trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    async with get_session() as session:
        if user_id and mode in (TradingModeEnum.PAPER, TradingModeEnum.BACKTEST):
            from db.cerberus_models import CerberusTrade

            paper_result = await session.execute(
                select(PaperTrade)
                .where(PaperTrade.user_id == user_id)
                .order_by(PaperTrade.entry_time.desc())
                .limit(max(limit * 3, 200))
            )
            normalized_trades = [_normalize_paper_trade(trade) for trade in paper_result.scalars().all()]

            cerberus_result = await session.execute(
                select(CerberusTrade)
                .where(CerberusTrade.user_id == user_id)
                .order_by(CerberusTrade.created_at.desc())
                .limit(max(limit * 3, 100))
            )
            cerberus_trades = cerberus_result.scalars().all()

            unmatched_cerberus: list[dict] = []
            for cerberus_trade in cerberus_trades:
                cerberus_time = cerberus_trade.entry_ts or cerberus_trade.created_at
                best_match_idx = None
                best_delta = None

                for idx, trade in enumerate(normalized_trades):
                    if trade.get("asset_type") != "stock":
                        continue
                    if trade.get("symbol", "").upper() != (cerberus_trade.symbol or "").upper():
                        continue
                    if trade.get("direction") != (cerberus_trade.side or "").lower():
                        continue
                    if abs(float(trade.get("quantity") or 0) - float(cerberus_trade.quantity or 0)) > 1e-6:
                        continue

                    trade_time_raw = trade.get("filled_at") or trade.get("submitted_at")
                    if not trade_time_raw or not cerberus_time:
                        continue

                    try:
                        trade_time = datetime.fromisoformat(str(trade_time_raw))
                    except ValueError:
                        continue

                    delta_seconds = abs((trade_time - cerberus_time).total_seconds())
                    if delta_seconds > 120:
                        continue

                    if best_delta is None or delta_seconds < best_delta:
                        best_match_idx = idx
                        best_delta = delta_seconds

                if best_match_idx is not None:
                    normalized_trades[best_match_idx]["source"] = "bot"
                    normalized_trades[best_match_idx]["bot_name"] = cerberus_trade.strategy_tag
                    normalized_trades[best_match_idx]["bot_explanation"] = _extract_bot_explanation(cerberus_trade)
                else:
                    unmatched_cerberus.append(_normalize_cerberus_trade(cerberus_trade))

            trades = normalized_trades + unmatched_cerberus
            trades.sort(key=_paper_trade_sort_key, reverse=True)
            return {"trades": trades[:limit], "mode": mode.value}

        stmt = (
            select(Trade)
            .where(Trade.mode == mode)
            .order_by(Trade.entry_time.desc())
            .limit(limit)
        )
        if user_id:
            stmt = stmt.where(Trade.user_id == user_id)

        result = await session.execute(
            stmt
        )
        trades = result.scalars().all()

        if trades:
            return {
                "trades": [
                    {
                        "id": str(t.id),
                        "symbol": t.symbol,
                        "asset_type": "stock",
                        "direction": "buy" if str(t.direction).lower().endswith("long") else "sell",
                        "quantity": t.quantity,
                        "order_type": "market",
                        "status": "filled" if (t.entry_time or t.exit_time) else "pending",
                        "filled_price": t.exit_price or t.entry_price,
                        "entry_price": t.entry_price,
                        "limit_price": None,
                        "stop_price": None,
                        "submitted_at": t.entry_time.isoformat() if t.entry_time else None,
                        "filled_at": (t.exit_time or t.entry_time).isoformat() if (t.exit_time or t.entry_time) else None,
                        "pnl": t.pnl,
                        "total_value": abs(float(t.quantity or 0)) * float(t.exit_price or t.entry_price or 0),
                        "source": "manual",
                        "bot_name": None,
                        "bot_explanation": None,
                    }
                    for t in trades
                ],
                "mode": mode.value,
            }

        if user_id:
            return {"trades": [], "mode": mode.value}

    # Fallback to executor log
    try:
        return _get_legacy_executor().get_trade_log(limit=limit)
    except Exception as exc:
        logger.warning("legacy_trade_log_failed", mode=mode.value, error=str(exc))
        return {"trades": [], "mode": mode.value}


@router.post("/switch-mode")
async def switch_mode(req: SwitchModeRequest, request: Request):
    """Switch trading mode (paper/live)."""
    user_id = getattr(request.state, "user_id", None)
    if user_id is not None:
        from api.routes.user_mode import SetModeRequest as UserSetModeRequest
        from api.routes.user_mode import set_mode as set_user_mode

        result = await set_user_mode(UserSetModeRequest(mode=req.mode), request)
        return {"status": "switched", "mode": result["mode"], "previous": result["previous"]}

    try:
        mode = TradingMode(req.mode)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {req.mode}")
    _get_legacy_executor().switch_mode(mode)
    return {"status": "switched", "mode": mode.value}


@router.get("/risk-events")
async def get_risk_events(request: Request, limit: int = Query(default=50, ge=1, le=200)):
    """Get recent risk events filtered by current trading mode."""
    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", None)
    events = _get_risk_manager(user_id).get_risk_events(limit=limit)
    if mode and isinstance(events, list):
        return [e for e in events if e.get("mode") == mode.value or "mode" not in e]
    return events


@router.post("/resume-trading")
async def resume_trading(request: Request):
    """Resume trading after a halt."""
    user_id = getattr(request.state, "user_id", None)
    _get_risk_manager(user_id).resume_trading()
    return {"status": "resumed"}


@router.get("/verify")
async def verify_transactions(request: Request):
    """Run transaction verification."""
    if not getattr(request.state, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    from services.security.verification import TransactionVerifier
    verifier = TransactionVerifier()
    try:
        report = verifier.verify_execution(_get_legacy_executor())
        return report
    except Exception as e:
        logger.exception("transaction_verification_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Verification failed")


@router.get("/bars")
async def get_bars(
    symbol: str = Query(..., min_length=1, max_length=32),
    timeframe: str = Query(default="1D", min_length=1, max_length=8),
    limit: int = Query(default=300, ge=50, le=1000),
    request: Request = None,
):
    """OHLCV bar data plus normalized indicator series for a symbol."""
    try:
        import pandas as pd
        import yfinance as yf

        normalized_tf = (timeframe or "1D").strip()
        tf_aliases = {
            "1m": "1m",
            "m1": "1m",
            "5m": "5m",
            "m5": "5m",
            "15m": "15m",
            "m15": "15m",
            "1H": "1H",
            "1h": "1H",
            "h1": "1H",
            "4H": "4H",
            "4h": "4H",
            "h4": "4H",
            "1D": "1D",
            "1d": "1D",
            "d1": "1D",
            "1W": "1W",
            "1w": "1W",
            "w1": "1W",
        }
        canonical_tf = tf_aliases.get(normalized_tf, "1D")
        period_map = {"1m": "2d", "5m": "10d", "15m": "30d", "1H": "90d", "4H": "180d", "1D": "2y", "1W": "5y"}
        interval_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1H": "60m", "4H": "60m", "1D": "1d", "1W": "1wk"}
        period = period_map[canonical_tf]
        interval = interval_map[canonical_tf]
        ticker = yf.Ticker(symbol.upper())
        hist = ticker.history(period=period, interval=interval)
        if hist.empty:
            return {"symbol": symbol, "bars": []}

        if canonical_tf == "4H":
            hist = (
                hist[["Open", "High", "Low", "Close", "Volume"]]
                .resample("4H")
                .agg({
                    "Open": "first",
                    "High": "max",
                    "Low": "min",
                    "Close": "last",
                    "Volume": "sum",
                })
                .dropna()
            )
            if hist.empty:
                return {"symbol": symbol, "bars": []}

        safe_limit = int(limit or 300)

        def _serialize_time(ts) -> int:
            return int(pd.Timestamp(ts).timestamp())

        bars = []
        for ts, row in hist.iterrows():
            volume_value = row["Volume"]
            bars.append({
                "time": _serialize_time(ts),
                "open": round(float(row["Open"]), 4),
                "high": round(float(row["High"]), 4),
                "low": round(float(row["Low"]), 4),
                "close": round(float(row["Close"]), 4),
                "volume": int(float(0 if pd.isna(volume_value) else volume_value)),
            })

        bars = bars[-safe_limit:]
        allowed_times = {bar["time"] for bar in bars}

        close_series = hist["Close"]
        rsi_series = IndicatorEngine.rsi(close_series, length=14)
        macd_series = IndicatorEngine.macd(close_series, fast=12, slow=26, signal=9)

        def _line_points(series) -> list[dict]:
            points: list[dict] = []
            for ts, value in series.items():
                if pd.isna(value):
                    continue
                time_value = _serialize_time(ts)
                if time_value not in allowed_times:
                    continue
                points.append({
                    "time": time_value,
                    "value": round(float(value), 4),
                })
            return points

        indicators = {
            "rsi": _line_points(rsi_series),
            "macd": {
                "macd": _line_points(macd_series["macd"]),
                "signal": _line_points(macd_series["signal"]),
                "histogram": _line_points(macd_series["histogram"]),
            },
        }
        return {"symbol": symbol.upper(), "timeframe": canonical_tf, "bars": bars, "indicators": indicators}
    except Exception as e:
        logger.exception("bars_fetch_failed", symbol=symbol.upper(), timeframe=timeframe, error=str(e))
        raise HTTPException(status_code=500, detail="Unable to load bar data")


@router.get("/portfolio-analytics")
async def get_portfolio_analytics(request: Request, symbols: Optional[str] = None):
    """Generate portfolio risk analytics report."""
    import pandas as pd
    from risk.analytics import PortfolioRiskAnalyzer
    analyzer = PortfolioRiskAnalyzer()

    # Get positions (Webull-aware)
    pos_data = await get_positions(request)
    positions = pos_data.get("positions", pos_data) if isinstance(pos_data, dict) else pos_data

    if symbols:
        requested = {s.strip().upper() for s in symbols.split(",")}
        positions = [p for p in positions if p.get("symbol", "").upper() in requested]

    if not positions:
        return analyzer.generate_risk_report([], pd.DataFrame())

    return analyzer.generate_risk_report(positions, pd.DataFrame())


# ---------------------------------------------------------------------------
# Equity history — portfolio equity curve over time
# ---------------------------------------------------------------------------


@router.get("/equity-history")
async def get_equity_history(
    request: Request,
    period: str = Query("1M", pattern="^(1D|1W|1M|3M|1Y|ALL)$"),
):
    """Return portfolio equity points over time for charting.

    Paper mode: reconstructs equity curve from paper trade history.
    Live mode: returns current equity as a single point (no historical snapshots yet).

    Returns ``{"points": [{"date": "...", "equity": ...}, ...], "initial_capital": ...}``
    """
    from datetime import timedelta

    user_id = getattr(request.state, "user_id", None)
    mode = getattr(request.state, "trading_mode", TradingModeEnum.PAPER)

    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    # Determine the lookback cutoff
    now = datetime.utcnow()
    period_map = {
        "1D": timedelta(days=1),
        "1W": timedelta(weeks=1),
        "1M": timedelta(days=30),
        "3M": timedelta(days=90),
        "1Y": timedelta(days=365),
        "ALL": timedelta(days=3650),
    }
    cutoff = now - period_map.get(period, timedelta(days=30))

    if mode == TradingModeEnum.PAPER or mode == TradingModeEnum.BACKTEST:
        return await _build_paper_equity_curve(user_id, cutoff, now)

    # Live mode — no historical snapshots stored yet, return current equity
    try:
        account_data = await get_account(request)
        current_equity = account_data.get("equity", 0)
        return {
            "points": [
                {"date": now.strftime("%Y-%m-%d"), "equity": current_equity},
            ],
            "initial_capital": current_equity,
        }
    except Exception as exc:
        logger.warning("live_equity_curve_failed", error=str(exc))
        return {"points": [], "initial_capital": 0, "data_unavailable": True}


async def _build_paper_equity_curve(
    user_id: int,
    cutoff: datetime,
    now: datetime,
) -> dict:
    """Reconstruct a paper portfolio equity curve from trade history.

    Strategy: walk through all paper trades chronologically, track cash +
    position values after each trade event, and emit equity snapshots.
    """
    async with get_session() as session:
        # Get portfolio
        result = await session.execute(
            select(PaperPortfolio).where(PaperPortfolio.user_id == user_id)
        )
        portfolio = result.scalar_one_or_none()

        if not portfolio:
            return {"points": [], "initial_capital": 1_000_000.0}

        initial_capital = portfolio.initial_capital or 1_000_000.0

        # Fetch ALL trades ordered chronologically (we need the full history
        # to reconstruct equity, then filter points by cutoff for display)
        trade_result = await session.execute(
            select(PaperTrade)
            .where(PaperTrade.portfolio_id == portfolio.id)
            .order_by(PaperTrade.entry_time.asc())
        )
        all_trades = trade_result.scalars().all()

        if not all_trades:
            # No trades — show flat line at initial capital
            return {
                "points": [
                    {"date": cutoff.strftime("%Y-%m-%dT%H:%M:%S"), "equity": initial_capital},
                    {"date": now.strftime("%Y-%m-%dT%H:%M:%S"), "equity": initial_capital},
                ],
                "initial_capital": initial_capital,
            }

        # Walk through trades and reconstruct equity at each trade event
        cash = initial_capital
        positions: dict[str, dict] = {}  # symbol -> {qty, avg_price}
        points: list[dict] = []

        # Add starting point
        first_trade_time = all_trades[0].entry_time or cutoff
        if first_trade_time > cutoff:
            points.append({
                "date": cutoff.strftime("%Y-%m-%dT%H:%M:%S"),
                "equity": initial_capital,
            })

        for trade in all_trades:
            trade_time = trade.entry_time or now
            multiplier = _position_multiplier(trade.symbol)
            direction = trade.direction
            qty = trade.quantity or 0
            price = trade.entry_price or 0

            # Closed trades (have PnL) — just apply the realized P&L to cash.
            # This avoids complex entry/exit cash simulation that breaks for
            # short round-trips where entry_price is the original credit price.
            if trade.status == PaperTradeStatus.CLOSED and trade.pnl is not None:
                cash += float(trade.pnl)

            elif direction == TradeDirection.LONG:
                # Open BUY — deduct cost, track position
                cost = qty * price * multiplier
                cash -= cost
                if trade.symbol in positions:
                    pos = positions[trade.symbol]
                    total_qty = pos["qty"] + qty
                    if total_qty > 0:
                        pos["avg_price"] = (
                            (pos["qty"] * pos["avg_price"] + qty * price) / total_qty
                        )
                    pos["qty"] = total_qty
                else:
                    positions[trade.symbol] = {"qty": qty, "avg_price": price, "multiplier": multiplier}

            elif direction == TradeDirection.SHORT:
                # Open SELL/SHORT — add proceeds, track negative position
                proceeds = qty * price * multiplier
                cash += proceeds
                if trade.symbol in positions:
                    positions[trade.symbol]["qty"] -= qty
                    if abs(positions[trade.symbol]["qty"]) <= 0.001:
                        del positions[trade.symbol]
                else:
                    positions[trade.symbol] = {"qty": -qty, "avg_price": price, "multiplier": multiplier}

            # Calculate total equity at this point
            positions_value = sum(
                abs(p["qty"]) * p.get("avg_price", 0) * p.get("multiplier", 1)
                * (1 if p["qty"] > 0 else -1)
                for p in positions.values()
            )
            equity = cash + positions_value

            points.append({
                "date": trade_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "equity": round(equity, 2),
            })

        # Add current point using the portfolio's actual current state
        pos_result = await session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        )
        current_positions = pos_result.scalars().all()
        current_positions_value = sum(
            (p.current_price or p.avg_entry_price) * p.quantity * _position_multiplier(p.symbol)
            for p in current_positions
        )
        current_equity = portfolio.cash + current_positions_value
        points.append({
            "date": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "equity": round(current_equity, 2),
        })

        # Filter to the requested period
        cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
        filtered_points = [p for p in points if p["date"] >= cutoff_str]

        # Ensure we always have at least the starting point
        if not filtered_points and points:
            filtered_points = [points[-1]]

        # Deduplicate by date (keep the last value for each date)
        seen: dict[str, dict] = {}
        for p in filtered_points:
            day_key = p["date"][:10]
            seen[day_key] = p
        deduped = sorted(seen.values(), key=lambda x: x["date"])

        return {
            "points": deduped,
            "initial_capital": initial_capital,
        }
