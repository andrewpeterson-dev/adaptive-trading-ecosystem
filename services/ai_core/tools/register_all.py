"""Register all copilot tools in the global registry."""
from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def register_all_tools():
    """Import all tool modules and call their registration functions."""
    from . import (
        portfolio_tools,
        risk_tools,
        market_tools,
        trading_tools,
        analytics_tools,
        research_tools,
    )

    portfolio_tools.register()
    risk_tools.register()
    market_tools.register()
    trading_tools.register()
    analytics_tools.register()
    research_tools.register()

    from .registry import get_registry
    count = len(get_registry().list_all())
    logger.info("all_tools_registered", count=count)
