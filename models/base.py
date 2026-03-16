"""
Abstract base class for all trading models.
Every model in the ecosystem must implement this interface.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class ModelMetrics:
    """Rolling performance metrics for a model."""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    num_trades: int = 0
    avg_trade_pnl: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "win_rate": self.win_rate,
            "profit_factor": self.profit_factor,
            "max_drawdown": self.max_drawdown,
            "total_return": self.total_return,
            "num_trades": self.num_trades,
            "avg_trade_pnl": self.avg_trade_pnl,
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class Signal:
    """A trading signal emitted by a model."""
    symbol: str
    direction: str          # "long", "short", "flat"
    strength: float         # 0.0 to 1.0 conviction
    model_name: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: dict = field(default_factory=dict)


class ModelBase(ABC):
    """
    Abstract base for all trading models.

    Subclasses must implement:
        train(df)        — fit model on historical data
        predict(df)      — generate signals from current data
        evaluate(df)     — compute performance metrics on held-out data
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.is_trained = False
        self.metrics = ModelMetrics()
        self._trade_log: list[dict] = []
        self._artifact = None

    # ── Required interface ───────────────────────────────────────────────

    @abstractmethod
    def train(self, df: pd.DataFrame, **kwargs) -> None:
        """Train or fit the model on historical data."""
        ...

    @abstractmethod
    def predict(self, df: pd.DataFrame) -> list[Signal]:
        """Generate trading signals from current market data."""
        ...

    @abstractmethod
    def evaluate(self, df: pd.DataFrame) -> ModelMetrics:
        """Evaluate model on held-out data and return performance metrics."""
        ...

    # ── Persistence ──────────────────────────────────────────────────────

    def save(self, directory: str = "artifacts") -> str:
        """Serialize model artifact to disk."""
        path = Path(directory) / f"{self.name}_v{self.version}.joblib"
        path.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self._artifact, path)
        logger.info("model_saved", name=self.name, path=str(path))
        return str(path)

    def load(self, path: str) -> None:
        """Load a saved model artifact."""
        self._artifact = joblib.load(path)
        self.is_trained = True
        logger.info("model_loaded", name=self.name, path=path)

    # ── Metrics helpers ──────────────────────────────────────────────────

    def update_metrics(self, returns: pd.Series) -> ModelMetrics:
        """Compute standard metrics from a return series."""
        if len(returns) < 2:
            return self.metrics

        # Filter to only bars where we had a position (non-zero return)
        active_returns = returns[returns != 0]
        all_returns = returns  # Keep full series for equity curve

        if len(active_returns) < 1:
            return self.metrics

        mean_ret = all_returns.mean()
        std_ret = all_returns.std()

        # Sharpe (annualized, assuming daily returns)
        self.metrics.sharpe_ratio = (
            (mean_ret / std_ret) * np.sqrt(252) if std_ret > 0 else 0.0
        )

        # Sortino
        downside = all_returns[all_returns < 0].std()
        self.metrics.sortino_ratio = (
            (mean_ret / downside) * np.sqrt(252) if downside > 0 else 0.0
        )

        # Win rate — only count bars where we were actually in a position
        if len(active_returns) > 0:
            self.metrics.win_rate = (active_returns > 0).mean()
        else:
            self.metrics.win_rate = 0.0

        # Profit factor
        gross_profit = active_returns[active_returns > 0].sum()
        gross_loss = abs(active_returns[active_returns < 0].sum())
        self.metrics.profit_factor = (
            gross_profit / gross_loss if gross_loss > 0 else float("inf")
        )

        # Max drawdown
        cumulative = (1 + all_returns).cumprod()
        rolling_max = cumulative.cummax()
        drawdown = (cumulative - rolling_max) / rolling_max
        self.metrics.max_drawdown = drawdown.min()

        # Total return
        self.metrics.total_return = cumulative.iloc[-1] - 1

        # Count actual trades (position changes, not bars)
        self.metrics.num_trades = len(active_returns)
        self.metrics.avg_trade_pnl = active_returns.mean() if len(active_returns) > 0 else 0.0
        self.metrics.last_updated = datetime.utcnow()

        return self.metrics

    def log_trade(self, trade: dict) -> None:
        """Append a trade record to the internal log."""
        trade["model_name"] = self.name
        trade["timestamp"] = datetime.utcnow().isoformat()
        self._trade_log.append(trade)

    def get_trade_log(self) -> list[dict]:
        return list(self._trade_log)

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name} v={self.version} trained={self.is_trained}>"
