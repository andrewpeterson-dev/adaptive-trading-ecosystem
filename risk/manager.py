"""
Risk management layer.
Enforces position limits, exposure caps, stop losses, drawdown shutdowns,
and trade frequency limits before any order reaches the execution engine.
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

import structlog

from config.settings import get_settings
from models.base import Signal

logger = structlog.get_logger(__name__)


class RiskViolation(Exception):
    """Raised when a proposed trade violates a risk rule."""
    pass


class RiskManager:
    """
    Gatekeeper between signal generation and order execution.
    Every trade proposal passes through here before execution.
    """

    def __init__(self):
        settings = get_settings()
        self.max_position_size_pct = settings.max_position_size_pct
        self.max_portfolio_exposure_pct = settings.max_portfolio_exposure_pct
        self.max_drawdown_pct = settings.max_drawdown_pct
        self.stop_loss_pct = settings.stop_loss_pct
        self.max_trades_per_hour = settings.max_trades_per_hour

        self._trade_timestamps: list[datetime] = []
        self._peak_equity: float = settings.initial_capital
        self._is_halted: bool = False
        self._halt_reason: Optional[str] = None
        self._open_positions: dict[str, dict] = {}
        self._risk_events: list[dict] = []

    # ── Signal quality gates ──────────────────────────────────────────────

    # Minimum signal strength to execute (filters weak/ambiguous signals)
    MIN_SIGNAL_STRENGTH: float = 0.25
    # Minimum model consensus required (fraction of models that must agree on direction)
    MIN_CONSENSUS_RATIO: float = 0.4
    # Models must have at least this many evaluated trades to be trusted
    MIN_TRADES_FOR_TRUST: int = 5
    # Reject signals from models with Sharpe below this threshold
    MIN_MODEL_SHARPE: float = -1.0
    # Maximum concentration: don't let one model's signal dominate if its weight is too low
    MIN_WEIGHT_TO_SIGNAL: float = 0.03

    def validate_signal_quality(
        self,
        signal: Signal,
        model_metrics: Optional[dict] = None,
        model_weight: float = 0.0,
        ensemble_signals: Optional[list[Signal]] = None,
    ) -> tuple[bool, str]:
        """
        Pre-execution quality gate for individual signals.
        Runs BEFORE position sizing and trade validation.
        Returns: (passes, rejection_reason)
        """
        # Gate 1: Minimum signal strength
        if signal.strength < self.MIN_SIGNAL_STRENGTH:
            reason = f"Signal too weak: {signal.strength:.3f} < {self.MIN_SIGNAL_STRENGTH}"
            self._log_event("signal_quality_gate", reason)
            return False, reason

        # Gate 2: Model must have enough track record
        if model_metrics:
            if model_metrics.get("num_trades", 0) < self.MIN_TRADES_FOR_TRUST:
                reason = f"Model {signal.model_name} has insufficient trades: {model_metrics.get('num_trades', 0)} < {self.MIN_TRADES_FOR_TRUST}"
                self._log_event("signal_quality_gate", reason)
                return False, reason

            # Gate 3: Model Sharpe floor
            sharpe = model_metrics.get("sharpe_ratio", 0)
            if sharpe < self.MIN_MODEL_SHARPE:
                reason = f"Model {signal.model_name} Sharpe too low: {sharpe:.3f} < {self.MIN_MODEL_SHARPE}"
                self._log_event("signal_quality_gate", reason)
                return False, reason

        # Gate 4: Model weight floor (don't execute from nearly-zero-weight models)
        if model_weight < self.MIN_WEIGHT_TO_SIGNAL:
            reason = f"Model {signal.model_name} weight too low: {model_weight:.3f} < {self.MIN_WEIGHT_TO_SIGNAL}"
            self._log_event("signal_quality_gate", reason)
            return False, reason

        # Gate 5: Consensus check — if ensemble signals provided, check agreement
        if ensemble_signals and len(ensemble_signals) >= 3:
            same_direction = sum(
                1 for s in ensemble_signals
                if s.direction == signal.direction and s.symbol == signal.symbol
            )
            total = sum(1 for s in ensemble_signals if s.symbol == signal.symbol)
            if total > 0:
                consensus = same_direction / total
                if consensus < self.MIN_CONSENSUS_RATIO:
                    reason = f"Low consensus for {signal.symbol} {signal.direction}: {consensus:.0%} < {self.MIN_CONSENSUS_RATIO:.0%}"
                    self._log_event("signal_quality_gate", reason)
                    return False, reason

        return True, "passed"

    def get_quality_gate_stats(self) -> dict:
        """Return stats on how many signals were rejected by quality gates."""
        gate_events = [e for e in self._risk_events if e["event_type"] == "signal_quality_gate"]
        return {
            "total_rejections": len(gate_events),
            "recent_rejections": [e for e in gate_events[-10:]],
        }

    # ── Pre-trade validation ─────────────────────────────────────────────

    def validate_trade(
        self,
        signal: Signal,
        proposed_size: float,
        current_equity: float,
        current_exposure: float,
        current_price: float,
    ) -> tuple[bool, float, str]:
        """
        Validate and potentially resize a proposed trade.
        Returns: (approved, adjusted_size, reason)
        """
        if self._is_halted:
            return False, 0.0, f"Trading halted: {self._halt_reason}"

        # 1. Max drawdown check
        if current_equity > self._peak_equity:
            self._peak_equity = current_equity
        drawdown = (self._peak_equity - current_equity) / self._peak_equity
        if drawdown >= self.max_drawdown_pct:
            self._halt_trading(f"Max drawdown breached: {drawdown:.2%} >= {self.max_drawdown_pct:.2%}")
            self._log_event("max_drawdown_breach", f"Drawdown {drawdown:.2%}")
            return False, 0.0, self._halt_reason

        # 2. Trade frequency limit
        now = datetime.utcnow()
        cutoff = now - timedelta(hours=1)
        self._trade_timestamps = [t for t in self._trade_timestamps if t > cutoff]
        if len(self._trade_timestamps) >= self.max_trades_per_hour:
            self._log_event("trade_frequency_limit", f"{len(self._trade_timestamps)} trades in last hour")
            return False, 0.0, f"Trade frequency limit: {self.max_trades_per_hour}/hr"

        # 3. Position size cap
        max_position_value = current_equity * self.max_position_size_pct
        trade_value = proposed_size * current_price
        if trade_value > max_position_value:
            adjusted_size = max_position_value / current_price
            logger.warning("position_size_capped", proposed=proposed_size, adjusted=adjusted_size)
            proposed_size = adjusted_size

        # 4. Portfolio exposure check
        new_exposure = current_exposure + (proposed_size * current_price)
        max_exposure = current_equity * self.max_portfolio_exposure_pct
        if new_exposure > max_exposure:
            remaining_capacity = max_exposure - current_exposure
            if remaining_capacity <= 0:
                self._log_event("exposure_limit_hit", f"Exposure at {current_exposure / current_equity:.2%}")
                return False, 0.0, "Max portfolio exposure reached"
            adjusted_size = remaining_capacity / current_price
            proposed_size = adjusted_size

        self._trade_timestamps.append(now)
        return True, proposed_size, "approved"

    # ── Position monitoring ──────────────────────────────────────────────

    def register_position(self, symbol: str, entry_price: float, size: float, direction: str) -> None:
        self._open_positions[symbol] = {
            "entry_price": entry_price,
            "size": size,
            "direction": direction,
            "entry_time": datetime.utcnow(),
        }

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """Returns True if stop loss is triggered and position should be closed."""
        if symbol not in self._open_positions:
            return False

        pos = self._open_positions[symbol]
        entry = pos["entry_price"]

        if pos["direction"] == "long":
            loss_pct = (entry - current_price) / entry
        else:
            loss_pct = (current_price - entry) / entry

        if loss_pct >= self.stop_loss_pct:
            self._log_event("stop_loss_triggered", f"{symbol} loss {loss_pct:.2%}")
            return True
        return False

    def close_position(self, symbol: str) -> Optional[dict]:
        return self._open_positions.pop(symbol, None)

    # ── System controls ──────────────────────────────────────────────────

    def _halt_trading(self, reason: str) -> None:
        self._is_halted = True
        self._halt_reason = reason
        logger.critical("trading_halted", reason=reason)

    def resume_trading(self) -> None:
        self._is_halted = False
        self._halt_reason = None
        logger.info("trading_resumed")

    @property
    def is_halted(self) -> bool:
        return self._is_halted

    # ── Risk event logging ───────────────────────────────────────────────

    def _log_event(self, event_type: str, description: str) -> None:
        event = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": event_type,
            "description": description,
        }
        self._risk_events.append(event)
        logger.warning("risk_event", **event)

    def get_risk_events(self, limit: int = 50) -> list[dict]:
        return self._risk_events[-limit:]

    def get_risk_summary(self, current_equity: float) -> dict:
        drawdown = (self._peak_equity - current_equity) / self._peak_equity if self._peak_equity > 0 else 0
        return {
            "is_halted": self._is_halted,
            "halt_reason": self._halt_reason,
            "current_drawdown_pct": drawdown,
            "max_drawdown_limit": self.max_drawdown_pct,
            "peak_equity": self._peak_equity,
            "open_positions": len(self._open_positions),
            "trades_last_hour": len(self._trade_timestamps),
            "recent_risk_events": len(self._risk_events),
        }
