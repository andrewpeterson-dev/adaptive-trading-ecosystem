"""Position sizing algorithms — fixed-fractional, Kelly, volatility-adjusted."""

from __future__ import annotations

import math

import structlog

logger = structlog.get_logger(__name__)


class PositionSizer:
    """Stateless position-sizing calculator."""

    # ------------------------------------------------------------------
    # Fixed-fractional (primary method)
    # ------------------------------------------------------------------
    @staticmethod
    def calculate_position_size(
        account_equity: float,
        entry_price: float,
        stop_price: float,
        risk_per_trade_pct: float = 1.0,
        max_position_pct: float = 10.0,
    ) -> int:
        """Return number of shares to buy using fixed-fractional risk sizing.

        ``risk_amount = equity * (risk_per_trade_pct / 100)``
        ``shares      = risk_amount / abs(entry_price - stop_price)``

        The result is capped so the total position value never exceeds
        ``max_position_pct`` of equity.

        Returns 0 when inputs are invalid rather than raising.
        """
        if account_equity <= 0 or entry_price <= 0 or stop_price <= 0:
            logger.warning(
                "position_size_invalid_inputs",
                equity=account_equity,
                entry=entry_price,
                stop=stop_price,
            )
            return 0

        risk_per_share = abs(entry_price - stop_price)
        if risk_per_share == 0:
            logger.warning("position_size_zero_risk", entry=entry_price, stop=stop_price)
            return 0

        risk_amount = account_equity * (risk_per_trade_pct / 100.0)
        shares_from_risk = risk_amount / risk_per_share

        # Cap by max position value
        max_position_value = account_equity * (max_position_pct / 100.0)
        shares_from_cap = max_position_value / entry_price

        shares = int(math.floor(min(shares_from_risk, shares_from_cap)))

        logger.debug(
            "position_size_calculated",
            shares=shares,
            risk_amount=round(risk_amount, 2),
            risk_per_share=round(risk_per_share, 2),
            max_value=round(max_position_value, 2),
        )
        return max(shares, 0)

    # ------------------------------------------------------------------
    # Kelly criterion
    # ------------------------------------------------------------------
    @staticmethod
    def kelly_criterion(
        win_rate: float,
        avg_win: float,
        avg_loss: float,
    ) -> float:
        """Return the Kelly-optimal fraction of equity to risk per trade.

        ``f* = (win_rate / avg_loss_ratio) - ((1 - win_rate) / avg_win_ratio)``

        Simplified: ``f* = win_rate - (1 - win_rate) / (avg_win / avg_loss)``

        Returns a float in [0, 1].  Negative Kelly (losing edge) returns 0.
        """
        if avg_loss <= 0 or avg_win <= 0:
            return 0.0
        if not 0.0 <= win_rate <= 1.0:
            return 0.0

        win_loss_ratio = avg_win / avg_loss
        kelly_f = win_rate - (1.0 - win_rate) / win_loss_ratio

        result = max(kelly_f, 0.0)
        logger.debug(
            "kelly_criterion",
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            kelly_fraction=round(result, 4),
        )
        return result

    # ------------------------------------------------------------------
    # Volatility-adjusted sizing (ATR-based)
    # ------------------------------------------------------------------
    @staticmethod
    def volatility_adjusted_size(
        account_equity: float,
        entry_price: float,
        atr: float,
        risk_per_trade_pct: float = 1.0,
        atr_multiplier: float = 2.0,
        max_position_pct: float = 10.0,
    ) -> int:
        """Return number of shares using ATR-based stop distance.

        ``stop_distance = atr * atr_multiplier``
        Then delegates to fixed-fractional sizing with that stop distance.

        Returns 0 when inputs are invalid.
        """
        if atr <= 0 or entry_price <= 0 or account_equity <= 0:
            logger.warning(
                "vol_size_invalid_inputs",
                equity=account_equity,
                entry=entry_price,
                atr=atr,
            )
            return 0

        stop_distance = atr * atr_multiplier
        stop_price = entry_price - stop_distance  # assumes long

        if stop_price <= 0:
            # ATR so large relative to price that no reasonable stop exists
            logger.warning("vol_size_stop_below_zero", entry=entry_price, stop=stop_price)
            return 0

        return PositionSizer.calculate_position_size(
            account_equity=account_equity,
            entry_price=entry_price,
            stop_price=stop_price,
            risk_per_trade_pct=risk_per_trade_pct,
            max_position_pct=max_position_pct,
        )
