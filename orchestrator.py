"""
Main orchestrator — the brain of the trading ecosystem.
Coordinates the full loop: data → models → signals → risk → execution → learning.
Runs as a scheduled loop alongside the API server.
"""

import asyncio
from datetime import datetime

import structlog

from allocation.capital import CapitalAllocator
from config.settings import get_settings
from data.ingestion import DataIngestor
from engine.executor import ExecutionEngine
from intelligence.meta import MetaLearner
from intelligence.regime import RegimeDetector, Regime
from intelligence.retrainer import ModelRetrainer
from models.ensemble import EnsembleMetaModel
from models.registry import create_default_models
from risk.manager import RiskManager

logger = structlog.get_logger(__name__)


class TradingOrchestrator:
    """
    Coordinates the full adaptive trading loop:
    1. Fetch latest data
    2. Detect market regime
    3. Check if retraining needed
    4. Generate signals from all models
    5. Aggregate via ensemble
    6. Pass through risk management
    7. Execute approved trades
    8. Update allocations
    9. Record performance for meta-learning
    """

    def __init__(self, symbols: list[str] = None):
        self.settings = get_settings()
        self.symbols = symbols or ["SPY", "QQQ", "IWM"]

        # Core components
        self.ingestor = DataIngestor()
        self.risk_manager = RiskManager()
        self.executor = ExecutionEngine(risk_manager=self.risk_manager)
        self.allocator = CapitalAllocator()
        self.regime_detector = RegimeDetector()
        self.retrainer = ModelRetrainer()
        self.meta_learner = MetaLearner()

        # Models
        self.models = create_default_models()
        self.ensemble = EnsembleMetaModel()
        for m in self.models:
            self.ensemble.register_model(m)

        self._running = False
        self._cycle_count = 0

    async def run_cycle(self) -> dict:
        """Execute one full trading cycle."""
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        logger.info("cycle_start", cycle=self._cycle_count)

        results = {"cycle": self._cycle_count, "timestamp": cycle_start.isoformat(), "actions": []}

        try:
            # 1. Fetch latest data
            for symbol in self.symbols:
                df = self.ingestor.fetch_and_cache(symbol, lookback_days=self.settings.walk_forward_window_days)

                if df.empty:
                    logger.warning("no_data", symbol=symbol)
                    continue

                # 2. Detect regime
                regime_result = self.regime_detector.detect(df)
                current_regime = Regime(regime_result["regime"])

                # 3. Check retraining
                retrain_results = self.retrainer.retrain_all(self.models, df)
                if any(retrain_results.values()):
                    results["actions"].append({"type": "retrain", "results": retrain_results})

                # 4. Record performance per regime
                self.meta_learner.record_all(current_regime, self.models)

                # 5. Get regime-aware weights
                recommended_weights = self.meta_learner.get_recommended_weights(current_regime, self.models)
                self.ensemble.model_weights = recommended_weights

                # 6. Generate ensemble signals
                signals = self.ensemble.predict(df)

                # 7. Execute signals
                account = self.executor.get_account()
                equity = account["equity"]
                positions = self.executor.get_positions()
                exposure = sum(abs(float(p["market_value"])) for p in positions)

                for signal in signals:
                    # Compute position size from allocation
                    allocation = self.allocator.get_allocation(signal.model_name)
                    if allocation <= 0:
                        allocation = equity * 0.05  # Default 5%

                    current_price = df["close"].iloc[-1]
                    quantity = allocation / current_price

                    order = self.executor.execute_signal(
                        signal=signal,
                        quantity=quantity,
                        current_price=current_price,
                        current_equity=equity,
                        current_exposure=exposure,
                    )
                    if order:
                        results["actions"].append({"type": "trade", "order": order})

            # 8. Update capital allocation
            self.allocator.update_capital(equity)
            self.allocator.compute_weights(self.models)
            results["allocation"] = self.allocator.get_allocation_summary()

            # 9. Compute regime weights for meta-learner
            self.meta_learner.compute_regime_weights(current_regime)

        except Exception as e:
            logger.error("cycle_error", error=str(e))
            results["error"] = str(e)

        elapsed = (datetime.utcnow() - cycle_start).total_seconds()
        results["elapsed_seconds"] = elapsed
        logger.info("cycle_complete", cycle=self._cycle_count, elapsed=elapsed)
        return results

    async def run_loop(self, interval_seconds: int = 60):
        """Run the trading loop continuously."""
        self._running = True
        logger.info("orchestrator_started", interval=interval_seconds, symbols=self.symbols)

        while self._running:
            try:
                await self.run_cycle()
            except Exception as e:
                logger.error("loop_error", error=str(e))
            await asyncio.sleep(interval_seconds)

    def stop(self):
        self._running = False
        logger.info("orchestrator_stopped")

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "cycles_completed": self._cycle_count,
            "symbols": self.symbols,
            "mode": self.settings.trading_mode.value,
            "models": [m.name for m in self.models],
            "allocation": self.allocator.get_allocation_summary(),
        }


async def main():
    """Entry point for running the orchestrator standalone."""
    orchestrator = TradingOrchestrator()
    await orchestrator.run_loop(interval_seconds=60)


if __name__ == "__main__":
    asyncio.run(main())
