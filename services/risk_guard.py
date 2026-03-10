"""Pre-trade risk checks — enforced before every order execution."""

from __future__ import annotations
from typing import Optional
from datetime import datetime

import structlog
from sqlalchemy import select, func

from db.database import get_session
from db.models import (
    UserRiskLimits, Trade, TradeStatus, TradingModeEnum, SystemEventType,
)
from services.event_logger import log_event

logger = structlog.get_logger(__name__)


class RiskViolation(Exception):
    """Raised when a risk limit would be breached."""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(reason)


async def check_pre_trade(
    user_id: int,
    mode: TradingModeEnum,
    order_value: float,
    total_equity: float,
    open_position_count: int,
    is_bot: bool = False,
) -> None:
    """
    Run all risk checks. Raises RiskViolation if any limit is breached.
    Call this before placing any order.
    """
    async with get_session() as db:
        result = await db.execute(
            select(UserRiskLimits).where(
                UserRiskLimits.user_id == user_id,
                UserRiskLimits.mode == mode,
            )
        )
        limits = result.scalar_one_or_none()

    if not limits:
        return  # No limits set — allow trade

    # 1. Kill switch
    if limits.kill_switch_active:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        "Kill switch is active — all trading halted", "critical")
        raise RiskViolation("Kill switch is active. All trading is halted.")

    # 2. Daily loss limit
    # TODO: Trade has no user_id column — query currently sums all users' trades.
    # Once Trade.user_id is added (requires migration), add .where(Trade.user_id == user_id).
    if limits.daily_loss_limit is not None:
        today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        async with get_session() as db:
            result = await db.execute(
                select(func.coalesce(func.sum(Trade.pnl), 0.0)).where(
                    Trade.mode == mode,
                    Trade.status == TradeStatus.FILLED,
                    Trade.exit_time >= today_start,
                )
            )
            daily_pnl = result.scalar() or 0.0

        if daily_pnl <= -abs(limits.daily_loss_limit):
            await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                            f"Daily loss limit hit: ${daily_pnl:.2f}", "warning")
            raise RiskViolation(
                f"Daily loss limit exceeded. Today's P&L: ${daily_pnl:.2f}, "
                f"limit: -${limits.daily_loss_limit:.2f}"
            )

    # 3. Max position size
    if total_equity > 0 and limits.max_position_size_pct:
        position_pct = order_value / total_equity
        if position_pct > limits.max_position_size_pct:
            await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                            f"Position size {position_pct:.1%} exceeds {limits.max_position_size_pct:.1%}", "warning")
            raise RiskViolation(
                f"Position size ({position_pct:.1%}) exceeds limit ({limits.max_position_size_pct:.1%})"
            )

    # 4. Max open positions
    if limits.max_open_positions and open_position_count >= limits.max_open_positions:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        f"Max open positions ({limits.max_open_positions}) reached", "warning")
        raise RiskViolation(f"Max open positions ({limits.max_open_positions}) reached")

    # 5. Live bot confirmation
    if is_bot and mode == TradingModeEnum.LIVE and not limits.live_bot_trading_confirmed:
        await log_event(user_id, SystemEventType.RISK_LIMIT_TRIGGERED, mode,
                        "Live bot trading not confirmed", "warning")
        raise RiskViolation(
            "Live automated trading has not been confirmed. "
            "Enable it in Settings > Risk Limits before running bots in live mode."
        )
