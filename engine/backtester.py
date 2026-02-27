"""
Backtesting engine with vectorbt integration.
Supports multi-model backtesting, walk-forward simulation, slippage, transaction costs,
and checkpoint/resume for long-running backtests.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Callable

import numpy as np
import pandas as pd
import structlog

from config.settings import get_settings
from models.base import ModelBase, ModelMetrics

logger = structlog.get_logger(__name__)

CHECKPOINT_DIR = Path("data/checkpoints")


class BacktestResult:
    """Container for backtest results."""

    def __init__(
        self,
        model_name: str,
        returns: pd.Series,
        equity_curve: pd.Series,
        trades: pd.DataFrame,
        metrics: ModelMetrics,
    ):
        self.model_name = model_name
        self.returns = returns
        self.equity_curve = equity_curve
        self.trades = trades
        self.metrics = metrics
        self.timestamp = datetime.utcnow()

    def to_dict(self) -> dict:
        return {
            "model_name": self.model_name,
            "sharpe_ratio": self.metrics.sharpe_ratio,
            "sortino_ratio": self.metrics.sortino_ratio,
            "win_rate": self.metrics.win_rate,
            "profit_factor": self.metrics.profit_factor,
            "max_drawdown": self.metrics.max_drawdown,
            "total_return": self.metrics.total_return,
            "num_trades": self.metrics.num_trades,
            "equity_final": float(self.equity_curve.iloc[-1]) if len(self.equity_curve) > 0 else 0,
        }


class BacktestEngine:
    """
    Backtesting engine supporting:
    - Single model backtest
    - Multi-model comparative backtest
    - Walk-forward simulation
    - Capital allocation simulation
    - Realistic slippage and transaction cost modeling
    """

    def __init__(
        self,
        initial_capital: float = None,
        slippage_bps: float = 5.0,
        commission_per_share: float = 0.005,
    ):
        settings = get_settings()
        self.initial_capital = initial_capital or settings.initial_capital
        self.slippage_bps = slippage_bps
        self.commission_per_share = commission_per_share
        self.results: list[BacktestResult] = []

    def run_backtest(
        self,
        model: ModelBase,
        df: pd.DataFrame,
        train_ratio: float = 0.7,
    ) -> BacktestResult:
        """
        Run a single-model backtest with train/test split.
        """
        split_idx = int(len(df) * train_ratio)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]

        # Train
        model.train(train_df)

        # Generate signals for test period (row by row simulation)
        positions = pd.Series(0.0, index=test_df.index)
        for i in range(len(test_df)):
            window = df.iloc[:split_idx + i + 1]  # Expanding window
            signals = model.predict(window)
            if signals:
                sig = signals[0]
                if sig.direction == "long":
                    positions.iloc[i] = sig.strength
                elif sig.direction == "short":
                    positions.iloc[i] = -sig.strength
                # "flat" stays 0

        # Compute returns with slippage and costs
        price_returns = test_df["close"].pct_change().fillna(0)
        strategy_returns = self._apply_costs(positions, price_returns, test_df["close"])

        # Equity curve
        equity_curve = self.initial_capital * (1 + strategy_returns).cumprod()

        # Build trades dataframe
        trades = self._extract_trades(positions, test_df)

        # Compute metrics
        metrics = model.update_metrics(strategy_returns.dropna())

        result = BacktestResult(
            model_name=model.name,
            returns=strategy_returns,
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
        )
        self.results.append(result)
        logger.info("backtest_complete", model=model.name, **result.to_dict())
        return result

    def run_multi_model_backtest(
        self,
        models: list[ModelBase],
        df: pd.DataFrame,
        capital_weights: Optional[dict[str, float]] = None,
    ) -> dict[str, BacktestResult]:
        """
        Run backtests for multiple models and aggregate results.
        Optionally simulates capital allocation across models.
        """
        if capital_weights is None:
            n = len(models)
            capital_weights = {m.name: 1.0 / n for m in models}

        results = {}
        for model in models:
            weight = capital_weights.get(model.name, 0.0)
            engine = BacktestEngine(
                initial_capital=self.initial_capital * weight,
                slippage_bps=self.slippage_bps,
                commission_per_share=self.commission_per_share,
            )
            result = engine.run_backtest(model, df)
            results[model.name] = result

        # Log comparative summary
        summary = {name: r.to_dict() for name, r in results.items()}
        logger.info("multi_model_backtest_complete", summary=summary)
        return results

    def run_walk_forward(
        self,
        model: ModelBase,
        df: pd.DataFrame,
        train_window: int = 200,
        test_window: int = 20,
    ) -> BacktestResult:
        """
        Walk-forward backtest: retrain periodically as new data arrives.
        """
        from data.ingestion import DataIngestor
        ingestor = DataIngestor()
        splits = ingestor.prepare_walk_forward_splits(df, train_window, test_window)

        all_returns = []
        all_equity = []
        equity = self.initial_capital

        for train_df, test_df in splits:
            model.train(train_df)

            # Predict on test fold
            positions = pd.Series(0.0, index=test_df.index)
            for i in range(len(test_df)):
                window = pd.concat([train_df, test_df.iloc[:i + 1]])
                signals = model.predict(window)
                if signals:
                    sig = signals[0]
                    if sig.direction == "long":
                        positions.iloc[i] = sig.strength
                    elif sig.direction == "short":
                        positions.iloc[i] = -sig.strength

            price_returns = test_df["close"].pct_change().fillna(0)
            fold_returns = self._apply_costs(positions, price_returns, test_df["close"])
            all_returns.append(fold_returns)

            equity *= (1 + fold_returns).prod()
            all_equity.extend([equity] * len(fold_returns))

        combined_returns = pd.concat(all_returns).reset_index(drop=True)
        equity_curve = pd.Series(all_equity)
        metrics = model.update_metrics(combined_returns.dropna())

        result = BacktestResult(
            model_name=f"{model.name}_wf",
            returns=combined_returns,
            equity_curve=equity_curve,
            trades=pd.DataFrame(),
            metrics=metrics,
        )
        self.results.append(result)
        logger.info("walk_forward_complete", model=model.name, **result.to_dict())
        return result

    # ── Cost modeling ────────────────────────────────────────────────────

    def _apply_costs(
        self,
        positions: pd.Series,
        price_returns: pd.Series,
        prices: pd.Series,
    ) -> pd.Series:
        """Apply slippage and commission to raw strategy returns."""
        # Raw strategy returns
        strategy_returns = positions.shift(1).fillna(0) * price_returns

        # Slippage: apply on position changes
        position_changes = positions.diff().abs().fillna(0)
        slippage_cost = position_changes * (self.slippage_bps / 10000)

        # Commission
        commission_cost = position_changes * self.commission_per_share / prices

        net_returns = strategy_returns - slippage_cost - commission_cost
        return net_returns

    def _extract_trades(self, positions: pd.Series, df: pd.DataFrame) -> pd.DataFrame:
        """Extract individual trades from position series."""
        changes = positions.diff().fillna(positions.iloc[0])
        trade_mask = changes != 0
        if not trade_mask.any():
            return pd.DataFrame()

        trades = df.loc[trade_mask, ["close"]].copy()
        trades["position_change"] = changes[trade_mask]
        trades["direction"] = trades["position_change"].apply(
            lambda x: "long" if x > 0 else "short" if x < 0 else "flat"
        )
        return trades

    def get_results_summary(self) -> list[dict]:
        return [r.to_dict() for r in self.results]

    # ── Checkpoint/Resume ─────────────────────────────────────────────────

    def run_backtest_with_checkpoints(
        self,
        model: ModelBase,
        df: pd.DataFrame,
        train_ratio: float = 0.7,
        checkpoint_interval: int = 50,
        progress_callback: Optional[Callable[[int, int, dict], None]] = None,
        resume_from: Optional[str] = None,
    ) -> BacktestResult:
        """
        Backtest with periodic checkpointing and optional resume.

        Args:
            checkpoint_interval: Save checkpoint every N bars
            progress_callback: Called with (current_bar, total_bars, partial_metrics)
            resume_from: Path to checkpoint file to resume from
        """
        split_idx = int(len(df) * train_ratio)
        train_df = df.iloc[:split_idx]
        test_df = df.iloc[split_idx:]
        total_bars = len(test_df)

        # Resume state or start fresh
        start_bar = 0
        positions_list = []

        if resume_from:
            checkpoint = self._load_checkpoint(resume_from)
            if checkpoint:
                start_bar = checkpoint["bar_index"]
                positions_list = checkpoint["positions"]
                logger.info("backtest_resumed", model=model.name, from_bar=start_bar)
            else:
                logger.warning("checkpoint_load_failed", path=resume_from)

        # Train model (always, even on resume — ensures consistent state)
        model.train(train_df)

        # Run simulation bar by bar
        checkpoint_path = None
        for i in range(start_bar, total_bars):
            window = df.iloc[:split_idx + i + 1]
            signals = model.predict(window)

            if signals:
                sig = signals[0]
                if sig.direction == "long":
                    positions_list.append(sig.strength)
                elif sig.direction == "short":
                    positions_list.append(-sig.strength)
                else:
                    positions_list.append(0.0)
            else:
                positions_list.append(0.0)

            # Checkpoint
            if (i + 1) % checkpoint_interval == 0 and i > start_bar:
                checkpoint_path = self._save_checkpoint(
                    model.name, i + 1, positions_list, split_idx
                )

            # Progress callback
            if progress_callback and (i % 10 == 0 or i == total_bars - 1):
                partial = self._compute_partial_metrics(
                    positions_list, test_df.iloc[:len(positions_list)]
                )
                progress_callback(i + 1, total_bars, partial)

        # Compute final results
        positions = pd.Series(positions_list, index=test_df.index[:len(positions_list)])
        price_returns = test_df["close"].iloc[:len(positions_list)].pct_change().fillna(0)
        strategy_returns = self._apply_costs(positions, price_returns, test_df["close"].iloc[:len(positions_list)])
        equity_curve = self.initial_capital * (1 + strategy_returns).cumprod()
        trades = self._extract_trades(positions, test_df.iloc[:len(positions_list)])
        metrics = model.update_metrics(strategy_returns.dropna())

        result = BacktestResult(
            model_name=model.name,
            returns=strategy_returns,
            equity_curve=equity_curve,
            trades=trades,
            metrics=metrics,
        )
        self.results.append(result)

        # Clean up checkpoint on successful completion
        if checkpoint_path:
            self._cleanup_checkpoint(checkpoint_path)

        logger.info("backtest_with_checkpoints_complete", model=model.name, bars=total_bars, **result.to_dict())
        return result

    def _save_checkpoint(
        self, model_name: str, bar_index: int, positions: list, split_idx: int
    ) -> str:
        """Save backtest state to disk."""
        CHECKPOINT_DIR.mkdir(parents=True, exist_ok=True)
        path = CHECKPOINT_DIR / f"{model_name}_{bar_index}.json"
        data = {
            "model_name": model_name,
            "bar_index": bar_index,
            "split_idx": split_idx,
            "positions": positions,
            "timestamp": datetime.utcnow().isoformat(),
        }
        path.write_text(json.dumps(data))
        logger.info("checkpoint_saved", path=str(path), bar=bar_index)
        return str(path)

    def _load_checkpoint(self, path: str) -> Optional[dict]:
        """Load checkpoint from disk."""
        try:
            return json.loads(Path(path).read_text())
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error("checkpoint_load_error", path=path, error=str(e))
            return None

    def _cleanup_checkpoint(self, path: str) -> None:
        """Remove checkpoint after successful completion."""
        try:
            Path(path).unlink(missing_ok=True)
        except OSError:
            pass

    def _compute_partial_metrics(
        self, positions: list, test_slice: pd.DataFrame
    ) -> dict:
        """Compute metrics from partial backtest for progress reporting."""
        if len(positions) < 2:
            return {"return_pct": 0, "bars_done": len(positions)}

        pos = pd.Series(positions, index=test_slice.index[:len(positions)])
        rets = test_slice["close"].pct_change().fillna(0) * pos.shift(1).fillna(0)
        cum_ret = (1 + rets).prod() - 1

        return {
            "return_pct": round(cum_ret * 100, 2),
            "bars_done": len(positions),
            "current_position": positions[-1] if positions else 0,
        }

    @staticmethod
    def list_checkpoints(model_name: Optional[str] = None) -> list[dict]:
        """List available checkpoint files."""
        if not CHECKPOINT_DIR.exists():
            return []
        checkpoints = []
        for path in sorted(CHECKPOINT_DIR.glob("*.json")):
            try:
                data = json.loads(path.read_text())
                if model_name and data.get("model_name") != model_name:
                    continue
                checkpoints.append({
                    "path": str(path),
                    "model_name": data["model_name"],
                    "bar_index": data["bar_index"],
                    "timestamp": data["timestamp"],
                })
            except (json.JSONDecodeError, KeyError):
                continue
        return checkpoints
