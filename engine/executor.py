"""
Execution engine — unified order execution for paper and live trading.
Abstracts Alpaca API into a clean interface with full audit trail.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

import structlog
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

from config.settings import get_settings, TradingMode
from models.base import Signal
from risk.manager import RiskManager
from services.security.audit import AuditLogger

logger = structlog.get_logger(__name__)


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"


class ExecutionEngine:
    """
    Handles order routing for paper and live modes.
    All orders pass through risk management before execution.
    """

    def __init__(self, risk_manager: RiskManager = None):
        settings = get_settings()
        self.mode = settings.trading_mode
        self.risk_manager = risk_manager or RiskManager()
        self._audit = AuditLogger()

        # Initialize Alpaca client
        is_paper = self.mode != TradingMode.LIVE
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=is_paper,
        )

        self._trade_log: list[dict] = []
        self._pending_orders: dict[str, dict] = {}

    # ── Order execution ──────────────────────────────────────────────────

    def execute_signal(
        self,
        signal: Signal,
        quantity: float,
        current_price: float,
        current_equity: float,
        current_exposure: float,
        order_type: OrderType = OrderType.MARKET,
        limit_price: Optional[float] = None,
        require_confirmation: bool = False,
    ) -> Optional[dict]:
        """
        Execute a trading signal after risk validation.
        Returns order info dict or None if rejected.

        For live mode, both settings.live_trading_enabled and
        require_confirmation must be True.
        """
        # Live mode safety gate
        if self.mode == TradingMode.LIVE:
            settings = get_settings()
            if not settings.live_trading_enabled or not require_confirmation:
                reason = "Live execution blocked: live_trading_enabled and require_confirmation both required"
                logger.warning("live_execution_blocked", symbol=signal.symbol, reason=reason)
                self._log_trade(signal, 0, "rejected", reason)
                return None

        if signal.direction == "flat":
            return self._close_position(signal.symbol)

        # Risk check
        approved, adjusted_qty, reason = self.risk_manager.validate_trade(
            signal=signal,
            proposed_size=quantity,
            current_equity=current_equity,
            current_exposure=current_exposure,
            current_price=current_price,
        )

        if not approved:
            logger.warning("trade_rejected", symbol=signal.symbol, reason=reason)
            self._log_trade(signal, 0, "rejected", reason)
            return None

        # Execute
        side = OrderSide.BUY if signal.direction == "long" else OrderSide.SELL

        try:
            if order_type == OrderType.MARKET:
                order_request = MarketOrderRequest(
                    symbol=signal.symbol,
                    qty=adjusted_qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                if limit_price is None:
                    limit_price = current_price
                order_request = LimitOrderRequest(
                    symbol=signal.symbol,
                    qty=adjusted_qty,
                    side=side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=limit_price,
                )

            order = self.client.submit_order(order_request)

            order_info = {
                "order_id": str(order.id),
                "symbol": signal.symbol,
                "side": signal.direction,
                "quantity": adjusted_qty,
                "order_type": order_type.value,
                "status": str(order.status),
                "model": signal.model_name,
                "signal_strength": signal.strength,
                "submitted_at": datetime.utcnow().isoformat(),
            }

            self._pending_orders[str(order.id)] = order_info
            self.risk_manager.register_position(
                signal.symbol, current_price, adjusted_qty, signal.direction
            )

            self._log_trade(signal, adjusted_qty, "submitted", str(order.id))
            logger.info("order_submitted", **order_info)
            return order_info

        except Exception as e:
            logger.error("order_failed", symbol=signal.symbol, error=str(e))
            self._log_trade(signal, 0, "error", str(e))
            return None

    def _close_position(self, symbol: str) -> Optional[dict]:
        """Close an open position."""
        try:
            self.client.close_position(symbol)
            self.risk_manager.close_position(symbol)
            result = {
                "symbol": symbol,
                "action": "close",
                "status": "submitted",
                "timestamp": datetime.utcnow().isoformat(),
            }
            logger.info("position_closed", symbol=symbol)
            return result
        except Exception as e:
            logger.error("close_failed", symbol=symbol, error=str(e))
            return None

    # ── Account info ─────────────────────────────────────────────────────

    def get_account(self) -> dict:
        """Get current account status."""
        account = self.client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "portfolio_value": float(account.portfolio_value),
            "status": str(account.status),
        }

    def get_positions(self) -> list[dict]:
        """Get all open positions."""
        positions = self.client.get_all_positions()
        return [
            {
                "symbol": p.symbol,
                "qty": float(p.qty),
                "side": p.side,
                "market_value": float(p.market_value),
                "unrealized_pl": float(p.unrealized_pl),
                "unrealized_plpc": float(p.unrealized_plpc),
                "current_price": float(p.current_price),
                "avg_entry_price": float(p.avg_entry_price),
            }
            for p in positions
        ]

    def get_orders(self, status: str = "open") -> list[dict]:
        """Get orders by status."""
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        request = GetOrdersRequest(status=status_map.get(status, QueryOrderStatus.OPEN))
        orders = self.client.get_orders(request)
        return [
            {
                "id": str(o.id),
                "symbol": o.symbol,
                "qty": float(o.qty) if o.qty else 0,
                "side": str(o.side),
                "type": str(o.type),
                "status": str(o.status),
                "submitted_at": str(o.submitted_at),
            }
            for o in orders
        ]

    # ── Mode management ──────────────────────────────────────────────────

    def switch_mode(self, new_mode: TradingMode) -> None:
        """Switch between paper and live trading."""
        if new_mode == TradingMode.LIVE and self.mode != TradingMode.LIVE:
            logger.critical("switching_to_live_trading")
        self.mode = new_mode
        is_paper = new_mode != TradingMode.LIVE
        settings = get_settings()
        self.client = TradingClient(
            api_key=settings.alpaca_api_key,
            secret_key=settings.alpaca_secret_key,
            paper=is_paper,
        )
        logger.info("mode_switched", new_mode=new_mode.value)

    # ── Audit trail ──────────────────────────────────────────────────────

    def _log_trade(self, signal: Signal, quantity: float, status: str, detail: str) -> None:
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "symbol": signal.symbol,
            "direction": signal.direction,
            "quantity": quantity,
            "model": signal.model_name,
            "strength": signal.strength,
            "status": status,
            "detail": detail,
            "mode": self.mode.value,
        }
        self._trade_log.append(entry)

        # Persist to audit log
        self._audit.log_trade(
            symbol=signal.symbol,
            direction=signal.direction,
            quantity=quantity,
            model=signal.model_name,
            signal_strength=signal.strength,
            status=status,
            mode=self.mode.value,
            order_id=detail if status == "submitted" else "",
            detail=detail,
        )

    def get_trade_log(self, limit: int = 100) -> list[dict]:
        return self._trade_log[-limit:]
