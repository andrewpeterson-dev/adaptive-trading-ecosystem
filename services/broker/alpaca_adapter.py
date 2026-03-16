"""Alpaca broker adapter -- paper and live trading via the alpaca-py SDK."""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from typing import Optional

import structlog

from config.settings import get_settings
from services.broker.base import (
    AccountInfo,
    BrokerAdapter,
    BrokerOrder,
    OrderResult,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    PositionSide,
    TimeInForce,
)

logger = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------

_SIDE_MAP = {
    OrderSide.BUY: "buy",
    OrderSide.SELL: "sell",
}

_TIF_MAP = {
    TimeInForce.DAY: "day",
    TimeInForce.GTC: "gtc",
    TimeInForce.IOC: "ioc",
    TimeInForce.FOK: "fok",
    TimeInForce.OPG: "opg",
    TimeInForce.CLS: "cls",
}


def _parse_float(value: object, default: float = 0.0) -> float:
    """Safely coerce an SDK value to float."""
    if value is None:
        return default
    try:
        return float(str(value))
    except (ValueError, TypeError):
        return default


def _parse_side(raw: str) -> OrderSide:
    normalized = raw.strip().lower()
    if normalized in ("buy", "buy_to_cover"):
        return OrderSide.BUY
    return OrderSide.SELL


def _parse_position_side(qty: float) -> PositionSide:
    return PositionSide.LONG if qty >= 0 else PositionSide.SHORT


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class AlpacaAdapter(BrokerAdapter):
    """Alpaca implementation of the broker adapter.

    Wraps the synchronous ``alpaca-py`` ``TradingClient`` with
    ``run_in_executor`` so the rest of the async stack is never blocked.
    """

    def __init__(self, *, api_key: str, secret_key: str, paper: bool = True) -> None:
        self._api_key = api_key
        self._secret_key = secret_key
        self._paper = paper
        self._client: Optional[object] = None

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        from alpaca.trading.client import TradingClient

        self._client = TradingClient(
            api_key=self._api_key,
            secret_key=self._secret_key,
            paper=self._paper,
        )
        # Validate credentials by fetching the account once.
        await self._run(self._client.get_account)
        logger.info(
            "alpaca_connected",
            paper=self._paper,
        )

    async def disconnect(self) -> None:
        self._client = None
        logger.info("alpaca_disconnected")

    # -- account -------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        self._ensure_connected()
        acct = await self._run(self._client.get_account)
        return AccountInfo(
            equity=_parse_float(acct.equity),
            buying_power=_parse_float(acct.buying_power),
            cash=_parse_float(acct.cash),
            margin_used=_parse_float(acct.initial_margin),
        )

    # -- positions -----------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        self._ensure_connected()
        raw = await self._run(self._client.get_all_positions)
        return [self._to_position(p) for p in raw]

    async def get_position(self, symbol: str) -> Position | None:
        self._ensure_connected()
        try:
            raw = await self._run(
                partial(self._client.get_open_position, symbol_or_asset_id=symbol),
            )
            return self._to_position(raw)
        except Exception:
            return None

    # -- orders --------------------------------------------------------------

    async def place_order(self, order: BrokerOrder) -> OrderResult:
        self._ensure_connected()
        from alpaca.trading.requests import (
            LimitOrderRequest,
            MarketOrderRequest,
            StopLimitOrderRequest,
            StopOrderRequest,
        )
        from alpaca.trading.enums import OrderSide as AlpSide, TimeInForce as AlpTIF

        side = AlpSide(_SIDE_MAP[order.side])
        tif = AlpTIF(_TIF_MAP[order.time_in_force])

        if order.order_type == OrderType.MARKET:
            req = MarketOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
            )
        elif order.order_type == OrderType.LIMIT:
            req = LimitOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
            )
        elif order.order_type == OrderType.STOP:
            req = StopOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
                stop_price=order.stop_price,
            )
        elif order.order_type == OrderType.STOP_LIMIT:
            req = StopLimitOrderRequest(
                symbol=order.symbol,
                qty=order.qty,
                side=side,
                time_in_force=tif,
                limit_price=order.limit_price,
                stop_price=order.stop_price,
            )
        else:
            raise ValueError(f"Unsupported order type: {order.order_type}")

        try:
            result = await self._run(partial(self._client.submit_order, order_data=req))
            logger.info(
                "alpaca_order_placed",
                order_id=str(result.id),
                symbol=order.symbol,
                side=order.side.value,
                qty=order.qty,
                paper=self._paper,
            )
            return OrderResult(
                order_id=str(result.id),
                status=str(result.status.value) if result.status else "new",
                filled_qty=_parse_float(result.filled_qty),
                filled_price=_parse_float(result.filled_avg_price),
            )
        except Exception as exc:
            logger.error(
                "alpaca_order_failed",
                symbol=order.symbol,
                error=str(exc),
            )
            return OrderResult(
                order_id="",
                status="rejected",
                filled_qty=0.0,
                filled_price=0.0,
                message=str(exc),
            )

    async def cancel_order(self, order_id: str) -> bool:
        self._ensure_connected()
        try:
            await self._run(partial(self._client.cancel_order_by_id, order_id=order_id))
            logger.info("alpaca_order_cancelled", order_id=order_id)
            return True
        except Exception as exc:
            logger.error("alpaca_cancel_failed", order_id=order_id, error=str(exc))
            return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        self._ensure_connected()
        raw = await self._run(partial(self._client.get_order_by_id, order_id=order_id))
        return self._to_order_status(raw)

    async def get_open_orders(self) -> list[OrderStatus]:
        self._ensure_connected()
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        req = GetOrdersRequest(status=QueryOrderStatus.OPEN)
        raw = await self._run(partial(self._client.get_orders, filter=req))
        return [self._to_order_status(o) for o in raw]

    # -- internal helpers ----------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("AlpacaAdapter is not connected. Call connect() first.")

    @staticmethod
    async def _run(fn, *args, **kwargs):
        """Run a synchronous SDK call in a thread-pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    @staticmethod
    def _to_position(raw) -> Position:
        qty = _parse_float(raw.qty)
        return Position(
            symbol=str(raw.symbol),
            qty=abs(qty),
            avg_cost=_parse_float(raw.avg_entry_price),
            market_value=_parse_float(raw.market_value),
            unrealized_pnl=_parse_float(raw.unrealized_pl),
            side=_parse_position_side(qty),
        )

    @staticmethod
    def _to_order_status(raw) -> OrderStatus:
        return OrderStatus(
            order_id=str(raw.id),
            symbol=str(raw.symbol),
            side=_parse_side(str(raw.side.value) if raw.side else "buy"),
            qty=_parse_float(raw.qty),
            filled_qty=_parse_float(raw.filled_qty),
            status=str(raw.status.value) if raw.status else "unknown",
            created_at=raw.created_at if isinstance(raw.created_at, datetime) else datetime.utcnow(),
        )


def build_alpaca_adapter(mode: str = "paper") -> AlpacaAdapter:
    """Construct an AlpacaAdapter from project settings.

    Parameters
    ----------
    mode : str
        ``"paper"`` or ``"live"``.  Determines which key-pair and URL to use.
    """
    settings = get_settings()
    is_paper = mode != "live"

    if is_paper:
        api_key = settings.paper_api_key or settings.alpaca_api_key
        secret_key = settings.paper_secret_key or settings.alpaca_secret_key
    else:
        api_key = settings.live_api_key or settings.alpaca_api_key
        secret_key = settings.live_secret_key or settings.alpaca_secret_key

    if not api_key or not secret_key:
        raise ValueError(
            f"Alpaca {mode} credentials not configured. "
            "Set PAPER_API_KEY / PAPER_SECRET_KEY (or ALPACA_API_KEY / ALPACA_SECRET_KEY) in .env."
        )

    return AlpacaAdapter(api_key=api_key, secret_key=secret_key, paper=is_paper)
