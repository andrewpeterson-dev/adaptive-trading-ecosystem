"""
Stop-loss, take-profit, trailing-stop, and time-based exit tracker.

Evaluates a position against a StopConfig and returns a StopSignal when
an exit condition is met.  Maintains per-symbol high-water marks for
trailing-stop calculations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StopConfig:
    """Exit-rule configuration for a single position.

    Values are percentages expressed as floats (e.g. 3.0 means 3 %).
    ``trailing_stop_pct`` is optional — set to ``None`` to disable trailing.
    """

    stop_loss_pct: float = 3.0
    take_profit_pct: float = 10.0
    trailing_stop_pct: float | None = None
    max_hold_hours: float = 168.0       # 1 week
    emergency_loss_pct: float = 10.0    # force-exit regardless of other rules

    @classmethod
    def from_bot_config(cls, config: dict) -> StopConfig:
        """Extract a StopConfig from a bot's strategy ``config_json``.

        Looks for keys at the top level and inside ``"risk"`` / ``"exits"``
        sub-dicts.  Missing keys fall back to class defaults.
        """
        # Merge top-level and nested dicts so we find values wherever they live
        merged: dict = {}
        merged.update(config)
        for sub_key in ("risk", "exits", "exit_rules", "position_management"):
            sub = config.get(sub_key)
            if isinstance(sub, dict):
                merged.update(sub)

        def _pct(key: str, default: float | None) -> float | None:
            raw = merged.get(key)
            if raw is None:
                return default
            try:
                val = float(raw)
                # Normalise: if the user stored 0.03 instead of 3.0, convert
                if 0 < val < 1:
                    val *= 100.0
                return val
            except (TypeError, ValueError):
                return default

        return cls(
            stop_loss_pct=_pct("stop_loss_pct", cls.stop_loss_pct) or cls.stop_loss_pct,
            take_profit_pct=_pct("take_profit_pct", cls.take_profit_pct) or cls.take_profit_pct,
            trailing_stop_pct=_pct("trailing_stop_pct", cls.trailing_stop_pct),
            max_hold_hours=float(merged.get("max_hold_hours", cls.max_hold_hours) or cls.max_hold_hours),
            emergency_loss_pct=_pct("emergency_loss_pct", cls.emergency_loss_pct) or cls.emergency_loss_pct,
        )


@dataclass
class StopSignal:
    """Returned by ``StopTracker.check`` when an exit condition fires."""

    reason: str          # "stop_loss" | "take_profit" | "trailing_stop" | "time_exit" | "emergency"
    target_price: float  # price that triggered the exit
    urgency: str         # "immediate" | "next_check"
    detail: str = ""     # human-readable explanation


# ---------------------------------------------------------------------------
# Tracker
# ---------------------------------------------------------------------------

class StopTracker:
    """Tracks per-symbol high-water marks and evaluates stop conditions.

    Intended to be long-lived across monitor loops — the high-water state
    persists in memory and is only cleared when a position is closed or
    the process restarts.
    """

    def __init__(self) -> None:
        # symbol → highest observed price since entry
        self._high_water: dict[str, float] = {}

    # -- State management ---------------------------------------------------

    def update(self, symbol: str, current_price: float) -> None:
        """Update the high-water mark for *symbol*."""
        symbol = symbol.upper()
        prev = self._high_water.get(symbol, 0.0)
        if current_price > prev:
            self._high_water[symbol] = current_price

    def reset(self, symbol: str) -> None:
        """Clear tracked state for *symbol* (call after position exit)."""
        self._high_water.pop(symbol.upper(), None)

    def get_high_water(self, symbol: str) -> float | None:
        return self._high_water.get(symbol.upper())

    # -- Evaluation ---------------------------------------------------------

    def check(
        self,
        *,
        entry_price: float,
        current_price: float,
        side: str,
        config: StopConfig,
        entry_ts: datetime | None = None,
        symbol: str | None = None,
    ) -> StopSignal | None:
        """Evaluate all exit rules and return a ``StopSignal`` if triggered.

        Checks are evaluated in priority order so the most urgent fires first:
          1. Emergency loss
          2. Hard stop-loss
          3. Take-profit
          4. Trailing stop  (only if ``trailing_stop_pct`` is set)
          5. Time-based hold limit

        Parameters
        ----------
        entry_price : float
            Price at which the position was opened.
        current_price : float
            Latest market price.
        side : str
            ``"buy"`` (long) or ``"sell"`` (short).
        config : StopConfig
            The exit-rule configuration.
        entry_ts : datetime, optional
            Timestamp the position was opened (needed for time-based exit).
        symbol : str, optional
            Used to look up the trailing-stop high-water mark.
        """
        if entry_price <= 0 or current_price <= 0:
            return None

        is_long = side.lower() in ("buy", "long")
        pnl_pct = self._pnl_pct(entry_price, current_price, is_long)

        # 1. Emergency loss
        if config.emergency_loss_pct and pnl_pct <= -config.emergency_loss_pct:
            return StopSignal(
                reason="emergency",
                target_price=current_price,
                urgency="immediate",
                detail=(
                    f"Emergency exit: position down {pnl_pct:+.2f}% "
                    f"(threshold -{config.emergency_loss_pct:.1f}%)"
                ),
            )

        # 2. Hard stop-loss
        if config.stop_loss_pct and pnl_pct <= -config.stop_loss_pct:
            return StopSignal(
                reason="stop_loss",
                target_price=current_price,
                urgency="immediate",
                detail=(
                    f"Stop-loss hit: position down {pnl_pct:+.2f}% "
                    f"(stop at -{config.stop_loss_pct:.1f}%)"
                ),
            )

        # 3. Take-profit
        if config.take_profit_pct and pnl_pct >= config.take_profit_pct:
            return StopSignal(
                reason="take_profit",
                target_price=current_price,
                urgency="immediate",
                detail=(
                    f"Take-profit hit: position up {pnl_pct:+.2f}% "
                    f"(target +{config.take_profit_pct:.1f}%)"
                ),
            )

        # 4. Trailing stop
        if config.trailing_stop_pct is not None and symbol:
            hwm = self._high_water.get(symbol.upper(), entry_price)
            if is_long:
                trail_price = hwm * (1 - config.trailing_stop_pct / 100.0)
                if current_price <= trail_price:
                    drop_pct = (1 - current_price / hwm) * 100.0
                    return StopSignal(
                        reason="trailing_stop",
                        target_price=current_price,
                        urgency="immediate",
                        detail=(
                            f"Trailing stop hit: price {current_price:.2f} dropped "
                            f"{drop_pct:.2f}% from peak {hwm:.2f} "
                            f"(trail {config.trailing_stop_pct:.1f}%)"
                        ),
                    )
            else:
                # Short: trail upward — exit if price rises X% from the *low*
                lwm = hwm  # for shorts we actually want low-water; reuse field
                trail_price = lwm * (1 + config.trailing_stop_pct / 100.0)
                if current_price >= trail_price:
                    rise_pct = (current_price / lwm - 1) * 100.0
                    return StopSignal(
                        reason="trailing_stop",
                        target_price=current_price,
                        urgency="immediate",
                        detail=(
                            f"Trailing stop hit: price {current_price:.2f} rose "
                            f"{rise_pct:.2f}% from trough {lwm:.2f} "
                            f"(trail {config.trailing_stop_pct:.1f}%)"
                        ),
                    )

        # 5. Time-based exit
        if entry_ts and config.max_hold_hours:
            hold_duration = datetime.utcnow() - entry_ts
            max_hold = timedelta(hours=config.max_hold_hours)
            if hold_duration >= max_hold:
                hours_held = hold_duration.total_seconds() / 3600.0
                return StopSignal(
                    reason="time_exit",
                    target_price=current_price,
                    urgency="next_check",
                    detail=(
                        f"Max hold exceeded: held {hours_held:.1f}h "
                        f"(limit {config.max_hold_hours:.0f}h), PnL {pnl_pct:+.2f}%"
                    ),
                )

        return None

    # -- Helpers ------------------------------------------------------------

    @staticmethod
    def _pnl_pct(entry: float, current: float, is_long: bool) -> float:
        """Return unrealised PnL as a percentage."""
        if is_long:
            return (current - entry) / entry * 100.0
        return (entry - current) / entry * 100.0
