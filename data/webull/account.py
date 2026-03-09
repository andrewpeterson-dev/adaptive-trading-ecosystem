"""
Webull account client — balances, positions, open orders. Read-only.

All reads are strictly scoped to the account that matches the configured
trading mode (paper or real). No order placement capability here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, TypedDict

import structlog

if TYPE_CHECKING:
    from .config import _SDKHandle

logger = structlog.get_logger(__name__)


# ── Response types ────────────────────────────────────────────────────────────

class AccountSummary(TypedDict):
    account_id:        str
    mode:              str     # "paper" or "real"
    net_liquidation:   float
    total_market_value: float
    cash_balance:      float
    buying_power:      float
    unrealized_pnl:    float
    realized_pnl:      float


class Position(TypedDict):
    symbol:        str
    quantity:      float
    avg_cost:      float
    last_price:    float
    market_value:  float
    unrealized_pnl: float


class Order(TypedDict):
    order_id:        str
    client_order_id: str
    symbol:          str
    side:            str
    order_type:      str
    quantity:        float
    filled_qty:      float
    price:           float
    status:          str


# ── Client ────────────────────────────────────────────────────────────────────

class AccountClient:
    """
    Read-only account data client.

    Reads are always scoped to the account matching the configured mode
    (paper account for paper mode, real account for real mode). A paper-mode
    client cannot read a real account and vice versa.
    """

    def __init__(self, handle: _SDKHandle) -> None:
        self._h = handle

    # ── Internal ──────────────────────────────────────────────────────────

    def _ensure_connected(self) -> bool:
        if not self._h.connected:
            return self._h.connect().get("success", False)
        return True

    def _require_account(self) -> Optional[str]:
        """Return mode-scoped account ID or None if unavailable."""
        if not self._ensure_connected() or not self._h.api:
            return None
        return self._h.allowed_account

    # ── Public API ────────────────────────────────────────────────────────

    def get_summary(self) -> Optional[AccountSummary]:
        """
        Return balance summary for the current mode's account.

        Returns None (not raises) on API error so callers can degrade gracefully.
        """
        acct = self._require_account()
        if not acct:
            return None

        try:
            resp = self._h.api.account.get_account_balance(acct, "USD")
            if resp.status_code != 200:
                logger.warning(
                    "account_balance_bad_status",
                    mode=self._h.env.mode.value,
                    status=resp.status_code,
                )
                return None

            raw            = resp.json()
            currency_assets = raw.get("account_currency_assets", [])
            usd            = currency_assets[0] if currency_assets else {}

            return AccountSummary(
                account_id=acct,
                mode=self._h.env.mode.value,
                net_liquidation=float(
                    usd.get("net_liquidation_value", raw.get("net_liquidation", 0))
                ),
                total_market_value=float(
                    raw.get("total_market_value", usd.get("positions_market_value", 0))
                ),
                cash_balance=float(
                    raw.get("total_cash_balance", usd.get("cash_balance", 0))
                ),
                buying_power=float(
                    usd.get("cash_power", usd.get("margin_power", 0))
                ),
                unrealized_pnl=float(raw.get("unrealized_pnl", 0)),
                realized_pnl=float(raw.get("realized_pnl", 0)),
            )

        except Exception as exc:
            logger.error(
                "account_summary_failed", mode=self._h.env.mode.value, error=str(exc)
            )
            return None

    def get_positions(self) -> list[Position]:
        """Return open positions for the current mode's account."""
        acct = self._require_account()
        if not acct:
            return []

        try:
            resp = self._h.api.account.get_account_position(acct)
            if resp.status_code != 200:
                return []

            raw   = resp.json()
            items = raw.get(
                "holdings",
                raw if isinstance(raw, list)
                else raw.get("data", raw.get("positions", [])),
            )

            return [
                Position(
                    symbol=pos.get("symbol", pos.get("ticker", {}).get("symbol", "???")),
                    quantity=float(pos.get("qty", pos.get("position", 0))),
                    avg_cost=float(pos.get("cost_price", pos.get("costPrice", 0))),
                    last_price=float(pos.get("last_price", pos.get("lastPrice", 0))),
                    market_value=float(pos.get("market_value", pos.get("marketValue", 0))),
                    unrealized_pnl=float(
                        pos.get("unrealized_profit_loss", pos.get("unrealizedProfitLoss", 0))
                    ),
                )
                for pos in items
            ]

        except Exception as exc:
            logger.error(
                "positions_fetch_failed", mode=self._h.env.mode.value, error=str(exc)
            )
            return []

    def get_open_orders(self) -> list[Order]:
        """Return open/working orders for the current mode's account."""
        acct = self._require_account()
        if not acct:
            return []

        try:
            resp = self._h.api.order.get_order_list(acct)
            if resp.status_code != 200:
                return []

            raw   = resp.json()
            items = raw if isinstance(raw, list) else raw.get("data", [])

            return [
                Order(
                    order_id=o.get("order_id", o.get("orderId", "")),
                    client_order_id=o.get("client_order_id", o.get("clientOrderId", "")),
                    symbol=o.get("symbol", "???"),
                    side=o.get("side", o.get("action", "")),
                    order_type=o.get("order_type", o.get("orderType", "")),
                    quantity=float(o.get("qty", o.get("totalQuantity", 0))),
                    filled_qty=float(o.get("filled_qty", o.get("filledQuantity", 0))),
                    price=float(o.get("limit_price", o.get("lmtPrice", 0)) or 0),
                    status=o.get("status", o.get("statusStr", "")),
                )
                for o in items
            ]

        except Exception as exc:
            logger.error(
                "open_orders_fetch_failed", mode=self._h.env.mode.value, error=str(exc)
            )
            return []
