"""Abstract broker interface and shared data models.

All broker implementations (Alpaca, Webull, etc.) must conform to the
BrokerAdapter ABC. The dataclasses here are the canonical exchange format
between the broker layer and the rest of the system.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class OrderSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(str, Enum):
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class TimeInForce(str, Enum):
    DAY = "day"
    GTC = "gtc"
    IOC = "ioc"
    FOK = "fok"
    OPG = "opg"
    CLS = "cls"


class PositionSide(str, Enum):
    LONG = "long"
    SHORT = "short"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class AccountInfo:
    equity: float
    buying_power: float
    cash: float
    margin_used: float


@dataclass(frozen=True)
class Position:
    symbol: str
    qty: float
    avg_cost: float
    market_value: float
    unrealized_pnl: float
    side: PositionSide


@dataclass(frozen=True)
class BrokerOrder:
    symbol: str
    side: OrderSide
    qty: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    time_in_force: TimeInForce = TimeInForce.DAY
    extended_hours: bool = False


@dataclass(frozen=True)
class OrderResult:
    order_id: str
    status: str
    filled_qty: float
    filled_price: float
    message: str = ""


@dataclass(frozen=True)
class OrderStatus:
    order_id: str
    symbol: str
    side: OrderSide
    qty: float
    filled_qty: float
    status: str
    created_at: datetime = field(default_factory=datetime.utcnow)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BrokerAdapter(ABC):
    """Abstract broker interface -- all broker implementations must conform."""

    @abstractmethod
    async def connect(self) -> None:
        """Establish the connection / authenticate with the broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Tear down the broker connection and release resources."""

    @abstractmethod
    async def get_account(self) -> AccountInfo:
        """Return current account snapshot (equity, buying power, etc.)."""

    @abstractmethod
    async def get_positions(self) -> list[Position]:
        """Return all open positions."""

    @abstractmethod
    async def get_position(self, symbol: str) -> Position | None:
        """Return a single position by symbol, or None if not held."""

    @abstractmethod
    async def place_order(self, order: BrokerOrder) -> OrderResult:
        """Submit an order. Returns immediately with initial status."""

    @abstractmethod
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel an open order. Returns True if the cancel was accepted."""

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus:
        """Fetch the current status of a single order by ID."""

    @abstractmethod
    async def get_open_orders(self) -> list[OrderStatus]:
        """Return all orders that are still open / working."""
