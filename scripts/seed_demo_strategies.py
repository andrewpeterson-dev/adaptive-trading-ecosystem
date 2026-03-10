"""
Seed 3 demo strategies so the Quant Intelligence features are visible on first run.
Safe to call multiple times — skips if strategies already exist.
"""

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.database import get_session
from db.models import Strategy

logger = structlog.get_logger(__name__)

DEMO_STRATEGIES = [
    {
        "name": "RSI Momentum Swing",
        "description": (
            "Enters long positions when RSI drops below 30 (oversold) with confirming "
            "volume spike. Targets a 5% move with a tight 2% stop-loss. Best in "
            "low-volatility bull regimes. Uses a 14-period RSI on daily timeframe."
        ),
        "action": "BUY",
        "symbols": ["AAPL", "MSFT", "NVDA", "GOOGL"],
        "timeframe": "1D",
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "position_size_pct": 0.10,
        "conditions": [
            {"indicator": "RSI", "operator": "<", "value": 30},
            {"indicator": "VOLUME", "operator": ">", "value": 1.5},
        ],
        "diagnostics": {
            "win_rate": 0.61,
            "avg_win_pct": 0.048,
            "avg_loss_pct": 0.019,
            "sharpe": 1.82,
            "max_drawdown": 0.07,
            "total_return": 0.24,
            "num_trades": 47,
        },
    },
    {
        "name": "MACD Trend Follower",
        "description": (
            "Follows medium-term trends using a MACD signal-line crossover with a 200-day SMA "
            "trend filter. Rides momentum with a wider stop and higher profit target. "
            "Works well in high-volume trending markets. Uses 12/26/9 MACD settings."
        ),
        "action": "BUY",
        "symbols": ["SPY", "QQQ", "IWM"],
        "timeframe": "4H",
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.09,
        "position_size_pct": 0.12,
        "conditions": [
            {"indicator": "MACD", "operator": "crossover", "value": 0},
            {"indicator": "SMA_200", "operator": ">", "value": "price"},
        ],
        "diagnostics": {
            "win_rate": 0.54,
            "avg_win_pct": 0.082,
            "avg_loss_pct": 0.028,
            "sharpe": 2.15,
            "max_drawdown": 0.12,
            "total_return": 0.38,
            "num_trades": 29,
        },
    },
    {
        "name": "Mean Reversion Alpha",
        "description": (
            "Fades extended moves by entering counter-trend when RSI exceeds 72 and price "
            "touches the upper Bollinger Band. Profits from mean-reversion in range-bound "
            "or high-volatility sideways regimes. Exits quickly — 3-day maximum hold."
        ),
        "action": "SELL",
        "symbols": ["TSLA", "AMD", "META", "COIN"],
        "timeframe": "1H",
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.04,
        "position_size_pct": 0.08,
        "conditions": [
            {"indicator": "RSI", "operator": ">", "value": 72},
            {"indicator": "BB_UPPER", "operator": "touch", "value": "price"},
        ],
        "diagnostics": {
            "win_rate": 0.67,
            "avg_win_pct": 0.036,
            "avg_loss_pct": 0.022,
            "sharpe": 1.56,
            "max_drawdown": 0.05,
            "total_return": 0.19,
            "num_trades": 63,
        },
    },
]


async def seed() -> None:
    """Insert demo strategies if the strategies table is empty."""
    async with get_session() as db:
        result = await db.execute(select(Strategy).limit(1))
        if result.scalar_one_or_none() is not None:
            return  # already have strategies

        for spec in DEMO_STRATEGIES:
            db.add(Strategy(**spec))

        await db.commit()
        logger.info("seeded_demo_strategies", count=len(DEMO_STRATEGIES))
