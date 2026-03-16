"""RiskEngine — unified pre-trade, portfolio-health, and market-condition checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from services.risk_engine.circuit_breaker import (
    BotCircuitBreaker,
    MarketCircuitBreaker,
)
from services.risk_engine.config import RiskConfig
from services.risk_engine.position_sizer import PositionSizer

logger = structlog.get_logger(__name__)


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #

@dataclass
class TradeContext:
    """Everything the risk engine needs to evaluate a proposed trade."""
    user_id: int
    symbol: str
    side: str                           # "buy" | "sell"
    qty: int
    entry_price: float
    stop_price: float
    account_equity: float
    current_positions: list[dict] = field(default_factory=list)
    # Each position dict: {"symbol", "market_value", "sector", "bot_id", ...}
    vix: Optional[float] = None
    spy_change_pct: Optional[float] = None
    volume: int = 0
    spread_pct: float = 0.0
    bot_id: Optional[str] = None


@dataclass
class RiskCheckResult:
    """Outcome of a pre-trade risk check."""
    allowed: bool
    reasons: list[str] = field(default_factory=list)
    adjustments: dict = field(default_factory=dict)
    # adjustments examples: {"reduced_size": 50, "delay_seconds": 300}


@dataclass
class PortfolioHealthReport:
    """Full portfolio risk assessment."""
    total_exposure_pct: float = 0.0
    sector_breakdown: dict[str, float] = field(default_factory=dict)
    largest_position_pct: float = 0.0
    daily_pnl_pct: float = 0.0
    risk_score: float = 0.0  # 0 = no risk, 100 = maximum risk


@dataclass
class MarketConditionResult:
    """Market-wide risk assessment."""
    tradeable: bool = True
    risk_level: str = "normal"       # normal | elevated | high | extreme
    reduce_factor: float = 1.0       # multiply proposed size by this
    reasons: list[str] = field(default_factory=list)


@dataclass
class ExposureResult:
    """Exposure-limit check result."""
    allowed: bool = True
    current_exposure_pct: float = 0.0
    sector_exposure_pct: float = 0.0
    reasons: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Risk Engine
# --------------------------------------------------------------------------- #

class RiskEngine:
    """Standalone risk engine — no dependency on reasoning engine or bot runner.

    Usage::

        engine = RiskEngine()
        result = await engine.check_pre_trade(context)
        if not result.allowed:
            print(result.reasons)
    """

    def __init__(self, config: RiskConfig | None = None) -> None:
        self.config = config or RiskConfig()
        self.sizer = PositionSizer()
        self.market_cb = MarketCircuitBreaker(self.config)
        self.bot_cb = BotCircuitBreaker(self.config)

    # ------------------------------------------------------------------ #
    # Pre-trade gate
    # ------------------------------------------------------------------ #

    async def check_pre_trade(self, ctx: TradeContext) -> RiskCheckResult:
        """Run all risk checks before a trade.  Returns allow/deny with reasons."""
        reasons: list[str] = []
        adjustments: dict = {}

        # 0. Kill switch
        if self.config.kill_switch_active:
            return RiskCheckResult(
                allowed=False,
                reasons=["Kill switch is active -- all trading halted."],
            )

        # 1. Market conditions (VIX, circuit breakers)
        mc = self.check_market_conditions(ctx.vix, ctx.spy_change_pct)
        if not mc.tradeable:
            return RiskCheckResult(allowed=False, reasons=mc.reasons)
        if mc.reduce_factor < 1.0:
            adjustments["reduce_factor"] = mc.reduce_factor
            reasons.extend(mc.reasons)

        # 2. Liquidity
        if not self.check_liquidity(ctx.volume, ctx.spread_pct):
            liq_reasons: list[str] = []
            if ctx.volume < self.config.min_volume:
                liq_reasons.append(
                    f"Volume {ctx.volume:,} below minimum {self.config.min_volume:,}."
                )
            if ctx.spread_pct > self.config.max_spread_pct:
                liq_reasons.append(
                    f"Spread {ctx.spread_pct:.2f}% exceeds max {self.config.max_spread_pct:.1f}%."
                )
            return RiskCheckResult(allowed=False, reasons=liq_reasons)

        # 3. Exposure limits
        proposed_value = ctx.qty * ctx.entry_price
        exp = await self.check_exposure(
            ctx.user_id, ctx.symbol, proposed_value, ctx.account_equity, ctx.current_positions,
        )
        if not exp.allowed:
            return RiskCheckResult(allowed=False, reasons=exp.reasons)
        reasons.extend(exp.reasons)

        # 4. Position size sanity
        if ctx.account_equity > 0:
            position_pct = (proposed_value / ctx.account_equity) * 100.0
            if position_pct > self.config.max_single_position_pct:
                return RiskCheckResult(
                    allowed=False,
                    reasons=[
                        f"Position {position_pct:.1f}% exceeds max "
                        f"{self.config.max_single_position_pct:.1f}%."
                    ],
                )

        # 5. Per-bot circuit breaker
        if ctx.bot_id and self.bot_cb.is_paused(ctx.bot_id):
            state = self.bot_cb.get_state(ctx.bot_id)
            return RiskCheckResult(
                allowed=False,
                reasons=[
                    f"Bot {ctx.bot_id} paused after {state.consecutive_losses} "
                    f"consecutive losses until {state.paused_until}."
                ],
            )

        # 6. Compute recommended size via sizer (informational adjustment)
        recommended = self.sizer.calculate_position_size(
            account_equity=ctx.account_equity,
            entry_price=ctx.entry_price,
            stop_price=ctx.stop_price,
            risk_per_trade_pct=1.0,  # default 1% risk
            max_position_pct=self.config.max_single_position_pct,
        )
        if recommended < ctx.qty:
            adjustments["recommended_size"] = recommended
            reasons.append(
                f"Requested {ctx.qty} shares exceeds risk-sized {recommended}."
            )

        # Apply reduce factor from market conditions
        if "reduce_factor" in adjustments and recommended > 0:
            reduced = int(recommended * adjustments["reduce_factor"])
            adjustments["reduced_size"] = max(reduced, 0)

        logger.info(
            "pre_trade_check",
            user_id=ctx.user_id,
            symbol=ctx.symbol,
            allowed=True,
            reasons=reasons,
            adjustments=adjustments,
        )

        return RiskCheckResult(allowed=True, reasons=reasons, adjustments=adjustments)

    # ------------------------------------------------------------------ #
    # Portfolio health
    # ------------------------------------------------------------------ #

    async def check_portfolio_health(
        self,
        user_id: int,
        account_equity: float = 0.0,
        positions: list[dict] | None = None,
        daily_pnl: float = 0.0,
    ) -> PortfolioHealthReport:
        """Full portfolio risk assessment.

        ``positions`` is a list of dicts, each with at least
        ``{"symbol", "market_value"}`` and optionally ``"sector"``.
        """
        positions = positions or []
        report = PortfolioHealthReport()

        if account_equity <= 0:
            report.risk_score = 100.0
            return report

        # Total exposure
        total_value = sum(abs(p.get("market_value", 0.0)) for p in positions)
        report.total_exposure_pct = (total_value / account_equity) * 100.0

        # Sector breakdown
        sector_values: dict[str, float] = {}
        for p in positions:
            sector = p.get("sector", "Unknown")
            sector_values[sector] = sector_values.get(sector, 0.0) + abs(
                p.get("market_value", 0.0)
            )
        report.sector_breakdown = {
            s: round((v / account_equity) * 100.0, 2) for s, v in sector_values.items()
        }

        # Largest position
        if positions:
            largest = max(abs(p.get("market_value", 0.0)) for p in positions)
            report.largest_position_pct = (largest / account_equity) * 100.0

        # Daily P&L
        report.daily_pnl_pct = (daily_pnl / account_equity) * 100.0

        # Composite risk score (0-100)
        score = 0.0

        # Exposure contribution (0-30)
        exposure_ratio = report.total_exposure_pct / self.config.max_portfolio_exposure_pct
        score += min(exposure_ratio, 1.5) * 20.0

        # Concentration contribution (0-25)
        if report.sector_breakdown:
            max_sector = max(report.sector_breakdown.values())
            concentration_ratio = max_sector / self.config.max_sector_exposure_pct
            score += min(concentration_ratio, 1.5) * 16.7

        # Single-position contribution (0-20)
        position_ratio = report.largest_position_pct / self.config.max_single_position_pct
        score += min(position_ratio, 1.5) * 13.3

        # Daily loss contribution (0-25)
        if report.daily_pnl_pct < 0:
            loss_ratio = abs(report.daily_pnl_pct) / self.config.max_daily_loss_pct
            score += min(loss_ratio, 1.5) * 16.7

        report.risk_score = round(min(score, 100.0), 1)

        logger.info(
            "portfolio_health",
            user_id=user_id,
            exposure_pct=round(report.total_exposure_pct, 1),
            risk_score=report.risk_score,
        )

        return report

    # ------------------------------------------------------------------ #
    # Market conditions
    # ------------------------------------------------------------------ #

    def check_market_conditions(
        self,
        vix: float | None = None,
        spy_change_pct: float | None = None,
    ) -> MarketConditionResult:
        """Check market-wide conditions (VIX, circuit breakers)."""
        result = MarketConditionResult()

        # VIX checks
        if vix is not None:
            if vix >= self.config.vix_halt_threshold:
                result.tradeable = False
                result.risk_level = "extreme"
                result.reduce_factor = 0.0
                result.reasons.append(
                    f"VIX extreme ({vix:.1f}) >= {self.config.vix_halt_threshold} "
                    f"-- new entries blocked."
                )
                return result

            if vix >= self.config.vix_reduce_threshold:
                result.risk_level = "high"
                result.reduce_factor = self.config.vix_reduce_factor
                result.reasons.append(
                    f"VIX high ({vix:.1f}) >= {self.config.vix_reduce_threshold} "
                    f"-- size reduced to {self.config.vix_reduce_factor:.0%}."
                )
            elif vix >= 18.0:
                result.risk_level = "elevated"

        # SPY circuit breaker
        if spy_change_pct is not None:
            cb_state = self.market_cb.update(spy_change_pct)
            if cb_state.is_halted:
                result.tradeable = False
                result.risk_level = "extreme"
                result.reduce_factor = 0.0
                result.reasons.append(
                    f"Circuit breaker {cb_state.level.value}: SPY "
                    f"{spy_change_pct:+.1f}% -- trading halted."
                )
                if cb_state.resumes_at:
                    result.reasons.append(
                        f"Resumes at {cb_state.resumes_at.isoformat()}."
                    )

        return result

    # ------------------------------------------------------------------ #
    # Liquidity
    # ------------------------------------------------------------------ #

    def check_liquidity(self, volume: int, spread_pct: float) -> bool:
        """Return True if the instrument has sufficient liquidity."""
        if volume < self.config.min_volume:
            logger.debug(
                "liquidity_fail_volume",
                volume=volume,
                min_volume=self.config.min_volume,
            )
            return False
        if spread_pct > self.config.max_spread_pct:
            logger.debug(
                "liquidity_fail_spread",
                spread_pct=spread_pct,
                max_spread=self.config.max_spread_pct,
            )
            return False
        return True

    # ------------------------------------------------------------------ #
    # Exposure
    # ------------------------------------------------------------------ #

    async def check_exposure(
        self,
        user_id: int,
        symbol: str,
        proposed_value: float,
        account_equity: float = 0.0,
        positions: list[dict] | None = None,
    ) -> ExposureResult:
        """Check sector / position / portfolio exposure limits."""
        positions = positions or []
        result = ExposureResult()

        if account_equity <= 0:
            return result  # can't evaluate without equity

        # Current total exposure
        total_value = sum(abs(p.get("market_value", 0.0)) for p in positions)
        new_total = total_value + abs(proposed_value)
        result.current_exposure_pct = (new_total / account_equity) * 100.0

        # Portfolio exposure limit
        if result.current_exposure_pct > self.config.max_portfolio_exposure_pct:
            result.allowed = False
            result.reasons.append(
                f"Portfolio exposure {result.current_exposure_pct:.1f}% "
                f"would exceed max {self.config.max_portfolio_exposure_pct:.1f}%."
            )

        # Sector exposure (if sector info is available)
        # Look at existing positions to find sector for this symbol
        symbol_sector: str | None = None
        sector_total = 0.0
        for p in positions:
            if p.get("symbol", "").upper() == symbol.upper():
                symbol_sector = p.get("sector")
            if symbol_sector and p.get("sector") == symbol_sector:
                sector_total += abs(p.get("market_value", 0.0))

        if symbol_sector:
            new_sector_total = sector_total + abs(proposed_value)
            result.sector_exposure_pct = (new_sector_total / account_equity) * 100.0
            if result.sector_exposure_pct > self.config.max_sector_exposure_pct:
                result.allowed = False
                result.reasons.append(
                    f"Sector '{symbol_sector}' exposure "
                    f"{result.sector_exposure_pct:.1f}% would exceed max "
                    f"{self.config.max_sector_exposure_pct:.1f}%."
                )

        # Correlated positions check
        # Count how many positions share the same sector as the proposed trade
        if symbol_sector:
            correlated_count = sum(
                1 for p in positions if p.get("sector") == symbol_sector
            )
            if correlated_count >= self.config.max_correlated_positions:
                result.allowed = False
                result.reasons.append(
                    f"Already {correlated_count} positions in sector "
                    f"'{symbol_sector}' (max {self.config.max_correlated_positions})."
                )

        logger.debug(
            "exposure_check",
            user_id=user_id,
            symbol=symbol,
            allowed=result.allowed,
            exposure_pct=round(result.current_exposure_pct, 1),
        )

        return result
