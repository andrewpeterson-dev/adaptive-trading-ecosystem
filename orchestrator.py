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
from intelligence.confidence_model import ConfidenceModel
from intelligence.decision_pipeline import DecisionPipeline
from intelligence.ensemble_engine import EnsembleEngine
from intelligence.llm_analyst import LLMAnalyst
from intelligence.llm_router import LLMRouter
from intelligence.meta import MetaLearner
from intelligence.ollama_client import OllamaClient
from intelligence.regime import RegimeDetector, Regime
from intelligence.retrainer import ModelRetrainer
from models.ensemble import EnsembleMetaModel
from models.registry import create_default_models
from news.ingestion import NewsIngestion
from news.report import SentimentReportGenerator
from news.sentiment import SentimentClassifier
from risk.analytics import PortfolioRiskAnalyzer
from risk.manager import RiskManager

logger = structlog.get_logger(__name__)


class TradingOrchestrator:
    """
    Coordinates the full adaptive trading loop:
    1. Fetch latest data
    2. Detect market regime
    3. Check if retraining needed
    4. Generate signals from all models
    5. Fetch news & classify sentiment
    6. Run LLM advisory analysis
    7. Score confidence (weighted: model + LLM + track record)
    8. Aggregate via ensemble with disagreement detection
    9. Route through decision pipeline (confidence → ensemble → risk)
    10. Execute approved trades
    11. Update allocations
    12. Record performance for meta-learning
    13. Periodic portfolio risk report
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

        # Intelligence components
        self.ollama_client = OllamaClient()
        self.llm_analyst = LLMAnalyst(ollama_client=self.ollama_client)
        self.llm_router = LLMRouter(settings=self.settings, ollama_client=self.ollama_client)
        self.confidence_model = ConfidenceModel()
        self.ensemble_engine = EnsembleEngine()
        self.decision_pipeline = DecisionPipeline(
            confidence_model=self.confidence_model,
            ensemble_engine=self.ensemble_engine,
            risk_manager=self.risk_manager,
        )

        # News & sentiment
        self.news_ingestion = NewsIngestion()
        self.sentiment_classifier = SentimentClassifier()
        self.sentiment_report_gen = SentimentReportGenerator()

        # Portfolio risk
        self.portfolio_analyzer = PortfolioRiskAnalyzer()

        self._running = False
        self._cycle_count = 0
        self._risk_report_interval = 10  # run portfolio risk every N cycles
        self._latest_sentiment_report = None
        self._latest_risk_report = None

    async def run_cycle(self) -> dict:
        """Execute one full trading cycle."""
        self._cycle_count += 1
        cycle_start = datetime.utcnow()
        logger.info("cycle_start", cycle=self._cycle_count)

        results = {"cycle": self._cycle_count, "timestamp": cycle_start.isoformat(), "actions": []}

        try:
            # ── Phase 1: News & Sentiment (across all symbols) ──────────
            symbol_sentiments = {}
            try:
                articles = self.news_ingestion.fetch_news(self.symbols)
                if articles:
                    for symbol in self.symbols:
                        symbol_articles = [
                            a for a in articles
                            if symbol in a.get("symbols", [])
                        ]
                        if symbol_articles:
                            classified = self.sentiment_classifier.classify_batch(
                                symbol_articles, symbol
                            )
                            symbol_sentiments[symbol] = classified

                    if symbol_sentiments:
                        self._latest_sentiment_report = (
                            self.sentiment_report_gen.generate(symbol_sentiments)
                        )
                        results["sentiment_report"] = self._latest_sentiment_report
                        logger.info(
                            "sentiment_phase_complete",
                            symbols_analyzed=len(symbol_sentiments),
                            mood=self._latest_sentiment_report.get("market_mood", "unknown"),
                        )
            except Exception as e:
                logger.warning("sentiment_phase_failed", error=str(e))

            # ── Phase 2: Per-symbol signal generation & intelligence ────
            for symbol in self.symbols:
                df = self.ingestor.fetch_and_cache(symbol, lookback_days=self.settings.walk_forward_window_days)

                if df.empty:
                    logger.warning("no_data", symbol=symbol)
                    continue

                # 2a. Detect regime
                regime_result = self.regime_detector.detect(df)
                current_regime = Regime(regime_result["regime"])

                # 2b. Check retraining
                retrain_results = self.retrainer.retrain_all(self.models, df)
                if any(retrain_results.values()):
                    results["actions"].append({"type": "retrain", "results": retrain_results})

                # 2c. Record performance per regime
                self.meta_learner.record_all(current_regime, self.models)

                # 2d. Get regime-aware weights
                recommended_weights = self.meta_learner.get_recommended_weights(current_regime, self.models)
                self.ensemble.model_weights = recommended_weights

                # 2e. LLM advisory analysis (rate-limited, not every cycle)
                llm_confidence = 0.0
                try:
                    if self.llm_analyst.should_reanalyze():
                        model_perf = [
                            {
                                "name": m.name,
                                "sharpe": m.metrics.sharpe_ratio,
                                "win_rate": m.metrics.win_rate,
                                "max_drawdown": m.metrics.max_drawdown,
                                "weight": recommended_weights.get(m.name, 0.0),
                            }
                            for m in self.models
                        ]
                        llm_analysis = self.llm_analyst.analyze(
                            df, regime_result, model_performance=model_perf
                        )
                        llm_confidence = self.llm_analyst.get_confidence_score()

                        # Apply LLM weight adjustments (advisory)
                        adjusted_weights = self.llm_analyst.apply_adjustments_to_weights(
                            recommended_weights, llm_analysis
                        )
                        self.ensemble.model_weights = adjusted_weights
                        logger.info(
                            "llm_analysis_applied",
                            symbol=symbol,
                            llm_confidence=llm_confidence,
                            regime=llm_analysis.regime_assessment,
                        )
                    else:
                        llm_confidence = self.llm_analyst.get_confidence_score()
                except Exception as e:
                    logger.warning("llm_analysis_failed", symbol=symbol, error=str(e))

                # 2f. Factor in news sentiment bias
                sentiment_bias = self._compute_sentiment_bias(symbol, symbol_sentiments)

                # 2g. Generate ensemble signals
                signals = self.ensemble.predict(df)

                # 2h. Route each signal through the decision pipeline
                account = self.executor.get_account()
                equity = account["equity"]
                positions = self.executor.get_positions()
                exposure = sum(abs(float(p["market_value"])) for p in positions)

                # Build prediction list from all models for ensemble engine
                all_model_predictions = [
                    {
                        "model": s.model_name,
                        "direction": s.direction,
                        "confidence": s.strength * 100.0,
                        "symbol": s.symbol,
                    }
                    for s in signals
                ]

                for signal in signals:
                    model_metrics = {}
                    for m in self.models:
                        if m.name == signal.model_name:
                            model_metrics = m.metrics.to_dict()
                            break

                    # Apply sentiment bias to signal strength (subtle adjustment)
                    adjusted_strength = signal.strength
                    if sentiment_bias != 0.0:
                        if signal.direction == "long" and sentiment_bias > 0:
                            adjusted_strength = min(1.0, signal.strength + sentiment_bias * 0.1)
                        elif signal.direction == "short" and sentiment_bias < 0:
                            adjusted_strength = min(1.0, signal.strength + abs(sentiment_bias) * 0.1)
                        elif signal.direction == "long" and sentiment_bias < 0:
                            adjusted_strength = max(0.0, signal.strength - abs(sentiment_bias) * 0.05)
                        elif signal.direction == "short" and sentiment_bias > 0:
                            adjusted_strength = max(0.0, signal.strength - sentiment_bias * 0.05)

                    # Run through decision pipeline
                    try:
                        decision = self.decision_pipeline.evaluate(
                            signal=signal,
                            llm_confidence=llm_confidence,
                            model_metrics=model_metrics,
                            regime=current_regime.value,
                            all_model_predictions=all_model_predictions,
                            model_weight=recommended_weights.get(signal.model_name, 0.1),
                            ensemble_signals=signals,
                        )

                        if not decision["approved"]:
                            logger.info(
                                "signal_blocked",
                                symbol=signal.symbol,
                                model=signal.model_name,
                                direction=signal.direction,
                                stage=decision["rejection_stage"],
                                reason=decision["rejection_reason"],
                            )
                            results["actions"].append({
                                "type": "blocked",
                                "symbol": signal.symbol,
                                "model": signal.model_name,
                                "stage": decision["rejection_stage"],
                                "reason": decision["rejection_reason"],
                            })
                            continue
                    except Exception as e:
                        logger.warning(
                            "decision_pipeline_error",
                            symbol=signal.symbol,
                            model=signal.model_name,
                            error=str(e),
                        )
                        # On pipeline error, fall through to existing execution
                        # which has its own risk checks in ExecutionEngine

                    # Signal approved — execute
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

            # ── Phase 3: Capital allocation update ──────────────────────
            self.allocator.update_capital(equity)
            self.allocator.compute_weights(self.models)
            results["allocation"] = self.allocator.get_allocation_summary()

            # ── Phase 4: Meta-learner regime weights ────────────────────
            self.meta_learner.compute_regime_weights(current_regime)

            # ── Phase 5: Periodic portfolio risk report ─────────────────
            if self._cycle_count % self._risk_report_interval == 0:
                try:
                    positions = self.executor.get_positions()
                    if positions:
                        # Build price history DataFrame from cached data
                        price_frames = {}
                        for symbol in self.symbols:
                            sym_df = self.ingestor.fetch_and_cache(
                                symbol, lookback_days=self.settings.walk_forward_window_days
                            )
                            if not sym_df.empty and "close" in sym_df.columns:
                                price_frames[symbol] = sym_df["close"]

                        if price_frames:
                            import pandas as pd
                            price_history = pd.DataFrame(price_frames).dropna()
                            portfolio_value = sum(
                                abs(float(p.get("market_value", 0))) for p in positions
                            )
                            self._latest_risk_report = (
                                self.portfolio_analyzer.generate_risk_report(
                                    positions=positions,
                                    price_history=price_history,
                                    portfolio_value=portfolio_value,
                                )
                            )
                            results["risk_report"] = self._latest_risk_report
                            logger.info(
                                "portfolio_risk_report",
                                rating=self._latest_risk_report.get("risk_rating"),
                                volatility=self._latest_risk_report.get("portfolio_volatility"),
                                var_95=self._latest_risk_report.get("var_95_pct"),
                            )
                except Exception as e:
                    logger.warning("portfolio_risk_report_failed", error=str(e))

        except Exception as e:
            logger.error("cycle_error", error=str(e))
            results["error"] = str(e)

        elapsed = (datetime.utcnow() - cycle_start).total_seconds()
        results["elapsed_seconds"] = elapsed
        logger.info("cycle_complete", cycle=self._cycle_count, elapsed=elapsed)
        return results

    def _compute_sentiment_bias(
        self, symbol: str, symbol_sentiments: dict[str, list[dict]]
    ) -> float:
        """
        Compute a sentiment bias for a symbol from classified news.
        Returns a value from -5 to +5 (weighted by relevance).
        Returns 0.0 if no sentiment data available.
        """
        classifications = symbol_sentiments.get(symbol, [])
        if not classifications:
            return 0.0

        weighted_sum = 0.0
        weight_total = 0.0
        for c in classifications:
            relevance = c.get("relevance", 0.5)
            score = c.get("score", 0.0)
            weighted_sum += score * relevance
            weight_total += relevance

        if weight_total <= 0:
            return 0.0

        return weighted_sum / weight_total

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
            "intelligence": {
                "llm_analyses": len(self.llm_analyst.get_history()),
                "decision_log_size": len(self.decision_pipeline.get_decision_log()),
                "sentiment_report": self._latest_sentiment_report is not None,
                "risk_report": self._latest_risk_report is not None,
                "ensemble_predictions": len(self.ensemble_engine.get_prediction_log()),
            },
        }


async def main():
    """Entry point for running the orchestrator standalone."""
    orchestrator = TradingOrchestrator()
    await orchestrator.run_loop(interval_seconds=60)


if __name__ == "__main__":
    asyncio.run(main())
