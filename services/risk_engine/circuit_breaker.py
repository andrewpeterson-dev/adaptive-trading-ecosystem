"""Circuit breakers — market-wide (SPY) and per-bot consecutive-loss halts."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import structlog

from services.risk_engine.config import RiskConfig

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #

class CircuitBreakerLevel(str, Enum):
    NONE = "none"
    LEVEL_1 = "level_1"   # SPY -7%
    LEVEL_2 = "level_2"   # SPY -13%
    LEVEL_3 = "level_3"   # SPY -20%


@dataclass
class CircuitBreakerState:
    """Snapshot of the current circuit-breaker status."""
    level: CircuitBreakerLevel = CircuitBreakerLevel.NONE
    triggered_at: Optional[datetime] = None
    resumes_at: Optional[datetime] = None
    spy_change_pct: float = 0.0

    @property
    def is_halted(self) -> bool:
        if self.level == CircuitBreakerLevel.NONE:
            return False
        if self.level == CircuitBreakerLevel.LEVEL_3:
            return True  # rest of day
        if self.resumes_at is None:
            return False
        return datetime.now(timezone.utc) < self.resumes_at


@dataclass
class BotCircuitBreakerState:
    """Per-bot consecutive-loss tracking."""
    bot_id: str
    consecutive_losses: int = 0
    paused_until: Optional[datetime] = None

    @property
    def is_paused(self) -> bool:
        if self.paused_until is None:
            return False
        return datetime.now(timezone.utc) < self.paused_until


# --------------------------------------------------------------------------- #
# Market circuit breaker
# --------------------------------------------------------------------------- #

class MarketCircuitBreaker:
    """Thread-safe SPY intraday circuit breaker.

    Maintains state across updates so multiple callers can query the
    current halt status without re-computing.
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self._config = config or RiskConfig()
        self._state = CircuitBreakerState()
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitBreakerState:
        with self._lock:
            return self._state

    def update(self, spy_change_pct: float) -> CircuitBreakerState:
        """Feed the latest SPY intraday change and return updated state.

        Levels are checked in order of severity (highest first) so that a
        single large drop triggers the correct level immediately.
        """
        thresholds = sorted(self._config.spy_circuit_breaker_pcts)
        now = datetime.now(timezone.utc)

        with self._lock:
            self._state.spy_change_pct = spy_change_pct

            # Only upgrade — never downgrade during the same day
            current_level = self._state.level

            if len(thresholds) >= 3 and spy_change_pct <= -thresholds[2]:
                if current_level != CircuitBreakerLevel.LEVEL_3:
                    self._state.level = CircuitBreakerLevel.LEVEL_3
                    self._state.triggered_at = now
                    self._state.resumes_at = None  # halted rest of day
                    logger.critical(
                        "circuit_breaker_level3",
                        spy_change_pct=spy_change_pct,
                        threshold=-thresholds[2],
                    )

            elif len(thresholds) >= 2 and spy_change_pct <= -thresholds[1]:
                if current_level not in (
                    CircuitBreakerLevel.LEVEL_2,
                    CircuitBreakerLevel.LEVEL_3,
                ):
                    self._state.level = CircuitBreakerLevel.LEVEL_2
                    self._state.triggered_at = now
                    self._state.resumes_at = now + timedelta(
                        minutes=self._config.spy_level2_halt_minutes,
                    )
                    logger.warning(
                        "circuit_breaker_level2",
                        spy_change_pct=spy_change_pct,
                        threshold=-thresholds[1],
                        resumes_at=self._state.resumes_at.isoformat(),
                    )

            elif len(thresholds) >= 1 and spy_change_pct <= -thresholds[0]:
                if current_level == CircuitBreakerLevel.NONE:
                    self._state.level = CircuitBreakerLevel.LEVEL_1
                    self._state.triggered_at = now
                    self._state.resumes_at = now + timedelta(
                        minutes=self._config.spy_level1_halt_minutes,
                    )
                    logger.warning(
                        "circuit_breaker_level1",
                        spy_change_pct=spy_change_pct,
                        threshold=-thresholds[0],
                        resumes_at=self._state.resumes_at.isoformat(),
                    )

            return self._state

    def reset(self) -> None:
        """Reset circuit breaker (e.g. at market open)."""
        with self._lock:
            self._state = CircuitBreakerState()
            logger.info("circuit_breaker_reset")


# --------------------------------------------------------------------------- #
# Per-bot circuit breaker
# --------------------------------------------------------------------------- #

class BotCircuitBreaker:
    """Thread-safe per-bot consecutive-loss circuit breaker."""

    def __init__(self, config: RiskConfig | None = None) -> None:
        self._config = config or RiskConfig()
        self._bots: dict[str, BotCircuitBreakerState] = {}
        self._lock = threading.Lock()

    def record_result(self, bot_id: str, is_loss: bool) -> BotCircuitBreakerState:
        """Record a trade result for a bot and return its updated state."""
        with self._lock:
            if bot_id not in self._bots:
                self._bots[bot_id] = BotCircuitBreakerState(bot_id=bot_id)

            state = self._bots[bot_id]

            if is_loss:
                state.consecutive_losses += 1
                if state.consecutive_losses >= self._config.bot_consecutive_loss_limit:
                    state.paused_until = datetime.now(timezone.utc) + timedelta(
                        minutes=self._config.bot_pause_minutes,
                    )
                    logger.warning(
                        "bot_circuit_breaker_triggered",
                        bot_id=bot_id,
                        consecutive_losses=state.consecutive_losses,
                        paused_until=state.paused_until.isoformat(),
                    )
            else:
                # A win resets the streak
                state.consecutive_losses = 0
                state.paused_until = None

            return state

    def get_state(self, bot_id: str) -> BotCircuitBreakerState:
        with self._lock:
            return self._bots.get(
                bot_id,
                BotCircuitBreakerState(bot_id=bot_id),
            )

    def is_paused(self, bot_id: str) -> bool:
        return self.get_state(bot_id).is_paused

    def reset(self, bot_id: str) -> None:
        """Manually reset a bot's circuit breaker."""
        with self._lock:
            self._bots.pop(bot_id, None)
            logger.info("bot_circuit_breaker_reset", bot_id=bot_id)

    def reset_all(self) -> None:
        with self._lock:
            self._bots.clear()
            logger.info("bot_circuit_breakers_reset_all")
