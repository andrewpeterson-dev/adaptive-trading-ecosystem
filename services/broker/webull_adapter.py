"""Webull broker adapter -- thin wrapper around the existing webull_client.

Delegates all SDK calls to ``data.webull_client`` (WebullPaperClient /
WebullLiveClient) and maps results into the canonical broker dataclasses.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from typing import Optional

import structlog

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

_ORDER_TYPE_TO_WEBULL = {
    OrderType.MARKET: "MKT",
    OrderType.LIMIT: "LMT",
    OrderType.STOP: "STP",
    OrderType.STOP_LIMIT: "STP_LMT",
}

_TIF_TO_WEBULL = {
    TimeInForce.DAY: "DAY",
    TimeInForce.GTC: "GTC",
    TimeInForce.IOC: "IOC",
    TimeInForce.FOK: "FOK",
    TimeInForce.OPG: "OPG",
    TimeInForce.CLS: "CLS",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _parse_side(raw: str) -> OrderSide:
    normalized = raw.strip().upper()
    if normalized in ("BUY", "BUY_TO_COVER"):
        return OrderSide.BUY
    return OrderSide.SELL


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------

class WebullAdapter(BrokerAdapter):
    """Webull implementation of the broker adapter.

    Wraps the synchronous ``WebullPaperClient`` / ``WebullLiveClient`` and
    runs all blocking SDK calls in a thread-pool executor.  The underlying
    Webull client handles account isolation (paper vs live).

    Parameters
    ----------
    app_key, app_secret : str
        Webull OpenAPI credentials.  Typically decrypted from the per-user
        ``broker_credentials`` DB table.
    mode : str
        ``"paper"`` (default) or ``"live"``.
    """

    def __init__(
        self,
        *,
        app_key: str,
        app_secret: str,
        mode: str = "paper",
        region: str = "us",
    ) -> None:
        self._app_key = app_key
        self._app_secret = app_secret
        self._mode = mode
        self._region = region
        self._client: Optional[object] = None

    # -- lifecycle -----------------------------------------------------------

    async def connect(self) -> None:
        from data.webull_client import WebullPaperClient, WebullLiveClient

        if self._mode == "live":
            self._client = WebullLiveClient(
                app_key=self._app_key,
                app_secret=self._app_secret,
                region=self._region,
            )
        else:
            self._client = WebullPaperClient(
                app_key=self._app_key,
                app_secret=self._app_secret,
                region=self._region,
            )

        result = await self._run(self._client.connect)
        if not result.get("success"):
            raise RuntimeError(f"Webull connect failed: {result.get('error', 'unknown')}")

        logger.info(
            "webull_adapter_connected",
            mode=self._mode,
            account_id=result.get("account_id"),
        )

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._run(self._client.disconnect)
        self._client = None
        logger.info("webull_adapter_disconnected")

    # -- account -------------------------------------------------------------

    async def get_account(self) -> AccountInfo:
        self._ensure_connected()
        summary = await self._run(self._client.get_account_summary)
        if summary is None:
            raise RuntimeError("Webull returned no account data. Check connection.")
        return AccountInfo(
            equity=_safe_float(summary.get("net_liquidation")),
            buying_power=_safe_float(summary.get("buying_power")),
            cash=_safe_float(summary.get("cash_balance")),
            margin_used=max(
                0.0,
                _safe_float(summary.get("net_liquidation"))
                - _safe_float(summary.get("cash_balance")),
            ),
        )

    # -- positions -----------------------------------------------------------

    async def get_positions(self) -> list[Position]:
        self._ensure_connected()
        raw_list = await self._run(self._client.get_positions)
        return [self._to_position(p) for p in raw_list]

    async def get_position(self, symbol: str) -> Position | None:
        positions = await self.get_positions()
        for pos in positions:
            if pos.symbol.upper() == symbol.upper():
                return pos
        return None

    # -- orders --------------------------------------------------------------

    async def place_order(self, order: BrokerOrder) -> OrderResult:
        self._ensure_connected()
        wb_side = order.side.value.upper()
        wb_type = _ORDER_TYPE_TO_WEBULL.get(order.order_type, "MKT")
        wb_tif = _TIF_TO_WEBULL.get(order.time_in_force, "DAY")

        try:
            result = await self._run(
                partial(
                    self._client.place_order,
                    symbol=order.symbol,
                    side=wb_side,
                    qty=int(order.qty),
                    order_type=wb_type,
                    limit_price=order.limit_price,
                    stop_price=order.stop_price,
                    tif=wb_tif,
                    user_confirmed=True,
                ),
            )

            if result.get("success"):
                logger.info(
                    "webull_order_placed",
                    order_id=result.get("order_id"),
                    symbol=order.symbol,
                    side=order.side.value,
                    qty=order.qty,
                    mode=self._mode,
                )
                return OrderResult(
                    order_id=str(result.get("order_id", result.get("client_order_id", ""))),
                    status="accepted",
                    filled_qty=0.0,
                    filled_price=0.0,
                )
            else:
                return OrderResult(
                    order_id="",
                    status="rejected",
                    filled_qty=0.0,
                    filled_price=0.0,
                    message=result.get("error", "Unknown Webull error"),
                )
        except Exception as exc:
            logger.error("webull_order_failed", symbol=order.symbol, error=str(exc))
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
            result = await self._run(partial(self._client.cancel_order, order_id))
            return result.get("success", False)
        except Exception as exc:
            logger.error("webull_cancel_failed", order_id=order_id, error=str(exc))
            return False

    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Fetch status for a single order by scanning the order list.

        The Webull SDK does not expose a single-order lookup, so we pull the
        full order list and filter.  This is acceptable because the list is
        typically short and cached server-side.
        """
        all_orders = await self.get_open_orders()
        for o in all_orders:
            if o.order_id == order_id:
                return o
        raise LookupError(f"Order {order_id} not found in Webull open orders")

    async def get_open_orders(self) -> list[OrderStatus]:
        self._ensure_connected()
        raw_list = await self._run(self._client.get_open_orders)
        return [self._to_order_status(o) for o in raw_list]

    # -- internal helpers ----------------------------------------------------

    def _ensure_connected(self) -> None:
        if self._client is None:
            raise RuntimeError("WebullAdapter is not connected. Call connect() first.")

    @staticmethod
    async def _run(fn, *args, **kwargs):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    @staticmethod
    def _to_position(raw: dict) -> Position:
        qty = _safe_float(raw.get("quantity", 0))
        return Position(
            symbol=raw.get("symbol", "???"),
            qty=abs(qty),
            avg_cost=_safe_float(raw.get("avg_cost")),
            market_value=_safe_float(raw.get("market_value")),
            unrealized_pnl=_safe_float(raw.get("unrealized_pnl")),
            side=PositionSide.LONG if qty >= 0 else PositionSide.SHORT,
        )

    @staticmethod
    def _to_order_status(raw: dict) -> OrderStatus:
        return OrderStatus(
            order_id=str(raw.get("order_id", raw.get("client_order_id", ""))),
            symbol=raw.get("symbol", "???"),
            side=_parse_side(raw.get("side", "BUY")),
            qty=_safe_float(raw.get("quantity")),
            filled_qty=_safe_float(raw.get("filled_qty")),
            status=raw.get("status", "unknown"),
            created_at=datetime.utcnow(),
        )
