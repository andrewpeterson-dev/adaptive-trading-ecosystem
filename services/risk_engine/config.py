"""Risk configuration — all thresholds in one place, no hardcoded values."""

from __future__ import annotations

from pydantic import BaseModel, Field


class RiskConfig(BaseModel):
    """All risk parameters in one place -- no more hardcoded thresholds."""

    # --- Drawdown ---
    max_daily_loss_pct: float = Field(
        default=5.0,
        description="Max allowable daily loss as % of equity before halting.",
    )
    max_weekly_loss_pct: float = Field(
        default=10.0,
        description="Max allowable weekly loss as % of equity before halting.",
    )
    max_total_drawdown_pct: float = Field(
        default=15.0,
        description="Max total drawdown from peak equity before kill switch.",
    )

    # --- Exposure ---
    max_single_position_pct: float = Field(
        default=10.0,
        description="Max single position size as % of equity.",
    )
    max_sector_exposure_pct: float = Field(
        default=30.0,
        description="Max combined exposure to a single sector as % of equity.",
    )
    max_portfolio_exposure_pct: float = Field(
        default=80.0,
        description="Max total portfolio exposure as % of equity.",
    )
    max_correlated_positions: int = Field(
        default=3,
        description="Max number of highly correlated open positions.",
    )

    # --- Volatility ---
    vix_halt_threshold: float = Field(
        default=40.0,
        description="VIX level above which all new entries are blocked.",
    )
    vix_reduce_threshold: float = Field(
        default=25.0,
        description="VIX level above which position sizes are reduced.",
    )
    vix_reduce_factor: float = Field(
        default=0.5,
        description="Multiply proposed size by this when VIX is elevated.",
    )

    # --- Circuit breakers ---
    spy_circuit_breaker_pcts: list[float] = Field(
        default=[7.0, 13.0, 20.0],
        description="SPY intraday drop thresholds (%) that trigger trading halts.",
    )
    spy_level1_halt_minutes: int = Field(
        default=15,
        description="Minutes to halt after level-1 circuit breaker (-7%).",
    )
    spy_level2_halt_minutes: int = Field(
        default=15,
        description="Minutes to halt after level-2 circuit breaker (-13%).",
    )
    # Level 3 (-20%) halts for the rest of the day (no configurable duration).

    bot_consecutive_loss_limit: int = Field(
        default=5,
        description="Pause a bot after this many consecutive losses.",
    )
    bot_pause_minutes: int = Field(
        default=60,
        description="Minutes to pause a bot after consecutive-loss trigger.",
    )

    # --- Liquidity ---
    min_volume: int = Field(
        default=10_000,
        description="Minimum daily volume required to trade an instrument.",
    )
    max_spread_pct: float = Field(
        default=2.0,
        description="Maximum bid-ask spread (%) allowed.",
    )

    # --- Rate limits ---
    max_trades_per_hour: int = Field(
        default=20,
        description="Max trades any single user/bot can execute per hour.",
    )
    max_orders_per_minute: int = Field(
        default=5,
        description="Max orders per minute to avoid broker rate limits.",
    )

    # --- Kill switch ---
    kill_switch_active: bool = Field(
        default=False,
        description="Global kill switch. When True, all trading is halted.",
    )
