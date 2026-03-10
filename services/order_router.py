"""
Order routing service.

Single source of truth for deciding which connection handles a given order.
Called by both paper_trading and trading routes. Never makes broker API calls.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Any
import structlog

logger = structlog.get_logger(__name__)


class OptionsNotSupportedError(Exception):
    def __init__(self, active_broker_name: str, available_providers: list = None):
        self.active_broker_name = active_broker_name
        self.available_providers = available_providers or []
        super().__init__(
            f"Options trading is not supported by {active_broker_name} paper. "
            "Enable options fallback in Settings → API Connections to proceed."
        )


@dataclass
class OrderRequest:
    symbol: str
    side: str
    qty: int
    instrument_type: str = "stock"
    option_type: Optional[str] = None
    strike: Optional[float] = None
    expiry: Optional[str] = None
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None
    tif: str = "DAY"
    user_confirmed: bool = False


@dataclass
class RouteResult:
    connection_id: int
    is_options_sim: bool = False


def validate_options_provider(connection: Any) -> None:
    provider = connection.provider
    if not provider.supports_options:
        raise ValueError(
            f"Provider '{provider.name}' does not support options trading. "
            "Choose a provider with supports_options=True (e.g. Tradier)."
        )
    if not provider.supports_paper:
        raise ValueError(f"Provider '{provider.name}' does not support paper trading.")


def resolve_route(
    req: OrderRequest,
    *,
    active_connection: Any,
    settings: Any,
    options_connection: Any,
) -> RouteResult:
    if req.instrument_type != "option":
        return RouteResult(connection_id=active_connection.id, is_options_sim=False)

    if active_connection.provider.supports_options:
        logger.info("options_routed_to_broker", broker=active_connection.provider.name, symbol=req.symbol)
        return RouteResult(connection_id=active_connection.id, is_options_sim=False)

    if settings.options_fallback_enabled and options_connection is not None:
        logger.info("options_routed_to_fallback", fallback=options_connection.provider.name,
                    symbol=req.symbol, strike=req.strike, option_type=req.option_type)
        return RouteResult(connection_id=options_connection.id, is_options_sim=True)

    raise OptionsNotSupportedError(active_broker_name=active_connection.provider.name)
