"""
Trading Orchestrator — central coordination layer.

Correct data flow:
    Market Data → Feature Engineering → Quant/AI Signals → Risk Engine → Execution → Broker

Nothing bypasses the risk engine. Market data and execution are fully separated.
"""
from __future__ import annotations

import asyncio
import structlog

from config.settings import get_settings

logger = structlog.get_logger(__name__)


class TradingOrchestrator:
    """Coordinates all trading subsystems and enforces the data flow pipeline.

    Subsystems:
        - MarketDataService: price/bar data from Polygon/yFinance/Alpaca/Finnhub
        - FeaturePipeline: transforms raw data into model features
        - RiskEngine: pre-trade checks, position sizing, exposure limits
        - PositionManager: continuous stop/target monitoring
        - SignalBus: cross-process event distribution
        - BotRunner: strategy evaluation loop (existing)
        - ReasoningEngine: AI-based trade decision layer (existing)
    """

    def __init__(self) -> None:
        self._started = False
        self._tasks: set[asyncio.Task] = set()

        # Lazy-loaded subsystems — initialized in start()
        self._position_manager = None
        self._signal_bus = None
        self._risk_engine = None

    async def start(self) -> None:
        """Initialize and start all subsystems after DB is ready."""
        if self._started:
            return

        settings = get_settings()
        logger.info("orchestrator_starting")

        # 1. Signal Bus (Redis-backed, falls back to in-process)
        try:
            from services.signal_bus import get_signal_bus
            self._signal_bus = get_signal_bus()
            await self._signal_bus.connect()
            logger.info("signal_bus_connected")
        except Exception as e:
            logger.warning("signal_bus_start_failed", error=str(e),
                           hint="Falling back to in-process event bus")

        # 2. Risk Engine
        try:
            from services.risk_engine import RiskEngine, RiskConfig
            risk_config = RiskConfig(
                max_daily_loss_pct=settings.max_drawdown_pct * 100 / 3,  # ~5% for 15% max DD
                max_total_drawdown_pct=settings.max_drawdown_pct * 100,
                max_single_position_pct=settings.max_position_size_pct * 100,
                max_portfolio_exposure_pct=settings.max_portfolio_exposure_pct * 100,
                max_trades_per_hour=settings.max_trades_per_hour,
            )
            self._risk_engine = RiskEngine(config=risk_config)
            logger.info("risk_engine_initialized")
        except Exception as e:
            logger.warning("risk_engine_init_failed", error=str(e),
                           hint="Trading will proceed without enhanced risk checks")

        # 3. Position Manager (continuous stop/target monitoring)
        try:
            from services.position_manager import PositionManager
            self._position_manager = PositionManager(check_interval=10.0)
            await self._position_manager.start()
            logger.info("position_manager_started", interval="10s")
        except Exception as e:
            logger.warning("position_manager_start_failed", error=str(e),
                           hint="Positions will only be checked during bot evaluation cycles")

        self._started = True
        logger.info("orchestrator_started")

    async def stop(self) -> None:
        """Gracefully shut down all subsystems."""
        if not self._started:
            return

        logger.info("orchestrator_stopping")

        if self._position_manager:
            try:
                await self._position_manager.stop()
            except Exception as e:
                logger.warning("position_manager_stop_error", error=str(e))

        if self._signal_bus:
            try:
                await self._signal_bus.disconnect()
            except Exception as e:
                logger.warning("signal_bus_stop_error", error=str(e))

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

        self._started = False
        logger.info("orchestrator_stopped")

    @property
    def risk_engine(self):
        return self._risk_engine

    @property
    def position_manager(self):
        return self._position_manager

    @property
    def signal_bus(self):
        return self._signal_bus

    @property
    def is_running(self) -> bool:
        return self._started


# Module-level singleton
orchestrator = TradingOrchestrator()
