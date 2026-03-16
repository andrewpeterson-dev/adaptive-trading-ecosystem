"""Broker abstraction layer -- unified interface for multiple broker backends."""

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
from services.broker.alpaca_adapter import AlpacaAdapter
from services.broker.webull_adapter import WebullAdapter
from services.broker.factory import close_all, close_broker, get_broker

__all__ = [
    # Abstract base + data models
    "AccountInfo",
    "BrokerAdapter",
    "BrokerOrder",
    "OrderResult",
    "OrderSide",
    "OrderStatus",
    "OrderType",
    "Position",
    "PositionSide",
    "TimeInForce",
    # Adapters
    "AlpacaAdapter",
    "WebullAdapter",
    # Factory
    "close_all",
    "close_broker",
    "get_broker",
]
