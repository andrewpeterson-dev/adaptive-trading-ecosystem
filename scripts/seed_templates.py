#!/usr/bin/env python3
"""
Seed the strategy_templates table with 12 built-in system templates.

Safe to re-run -- skips if system templates already exist.
Usage:  python -m scripts.seed_templates
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select, func
from db.database import get_session, init_db
from db.models import StrategyTemplate

SYSTEM_USER_ID = 1

SYSTEM_TEMPLATES = [
    # ── 1. RSI Mean Reversion ─────────────────────────────────────────────
    {
        "name": "RSI Mean Reversion",
        "description": (
            "Classic mean-reversion strategy that buys when RSI drops into oversold "
            "territory and sells when it reaches overbought levels. Works best in "
            "range-bound markets on broad index ETFs."
        ),
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.06,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "rsi", "operator": "<", "value": 30, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Entry Signal",
                "conditions": [
                    {"indicator": "rsi", "operator": "<", "value": 30, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Enters long when RSI(14) drops below 30, expecting a bounce back toward the mean. Exits on RSI overbought or take-profit.",
            "feature_signals": ["RSI(14) oversold detection", "Mean-reversion bounce targeting"],
            "assumptions": [
                "Market is range-bound or in a healthy uptrend with temporary pullbacks",
                "RSI below 30 historically precedes short-term reversals on SPY/QQQ",
                "Stop-loss at 3% limits downside in extended selloffs",
            ],
        },
    },
    # ── 2. Moving Average Crossover ───────────────────────────────────────
    {
        "name": "Moving Average Crossover",
        "description": (
            "Trend-following strategy that enters when the fast EMA(20) crosses above "
            "the slow EMA(50), signaling the start of a new uptrend. Best for liquid "
            "large-cap names on daily charts."
        ),
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["AAPL", "MSFT"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "ema", "operator": "crosses_above", "value": 0, "params": {"period": 20}, "compare_to": "ema_50", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Golden Cross",
                "conditions": [
                    {"indicator": "ema", "operator": "crosses_above", "value": 0, "params": {"period": 20}, "compare_to": "ema_50", "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Buys when EMA(20) crosses above EMA(50) -- a classic golden cross signal indicating emerging bullish momentum.",
            "feature_signals": ["EMA(20)/EMA(50) crossover", "Trend initiation detection"],
            "assumptions": [
                "Works best in trending markets, not choppy sideways action",
                "AAPL and MSFT exhibit strong trend-following behavior on daily charts",
                "8% take-profit captures the initial leg of the trend",
            ],
        },
    },
    # ── 3. Momentum Breakout ──────────────────────────────────────────────
    {
        "name": "Momentum Breakout",
        "description": (
            "Multi-signal breakout strategy combining RSI momentum, volume confirmation, "
            "and MACD trend alignment. Designed for hourly SPY trading to capture "
            "intraday breakouts with strong conviction."
        ),
        "strategy_type": "breakout",
        "action": "BUY",
        "timeframe": "1H",
        "symbols": ["SPY"],
        "stop_loss_pct": 0.015,
        "take_profit_pct": 0.04,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "rsi", "operator": ">", "value": 60, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 2000000, "params": {}, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Breakout Confirmation",
                "conditions": [
                    {"indicator": "rsi", "operator": ">", "value": 60, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "volume", "operator": ">", "value": 2000000, "params": {}, "action": "BUY"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Triple-confirmation breakout: RSI above 60 for momentum, volume above 2M for participation, and MACD positive for trend alignment.",
            "feature_signals": ["RSI(14) momentum filter", "Volume surge detection", "MACD trend confirmation"],
            "assumptions": [
                "All three signals must fire simultaneously for high-conviction entry",
                "Hourly timeframe balances signal quality with trade frequency on SPY",
                "1.5% stop-loss appropriate for intraday SPY moves",
            ],
        },
    },
    # ── 4. Bollinger Band Squeeze ─────────────────────────────────────────
    {
        "name": "Bollinger Band Squeeze",
        "description": (
            "Mean-reversion entry when price touches the lower Bollinger Band while "
            "RSI confirms oversold conditions. Targets the bounce back toward the "
            "middle band on 4-hour QQQ charts."
        ),
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "4H",
        "symbols": ["QQQ"],
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std": 2}, "field": "lower", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Oversold at Lower Band",
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std": 2}, "field": "lower", "action": "BUY"},
                    {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Buys when price drops below the lower Bollinger Band (20,2) while RSI(14) is below 35, expecting a reversion toward the moving average.",
            "feature_signals": ["Bollinger Band lower touch", "RSI(14) oversold confirmation"],
            "assumptions": [
                "Price at the lower band with RSI confirmation reduces false signals",
                "4H timeframe smooths noise while providing actionable entries on QQQ",
                "Targets the middle band (20-period SMA) as the profit zone",
            ],
        },
    },
    # ── 5. MACD Trend Follower ────────────────────────────────────────────
    {
        "name": "MACD Trend Follower",
        "description": (
            "Dual-confirmation trend strategy that requires both MACD above zero and "
            "EMA(20) trending upward. Diversified across three major index ETFs "
            "for broad market exposure."
        ),
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "IWM"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.07,
        "position_size_pct": 0.04,
        "conditions": [
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 20}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Trend Confirmation",
                "conditions": [
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 20}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Enters when MACD histogram is positive and EMA(20) slope is up, confirming a healthy uptrend across SPY, QQQ, and IWM.",
            "feature_signals": ["MACD positive histogram", "EMA(20) upward slope"],
            "assumptions": [
                "Dual indicator confirmation reduces whipsaw entries",
                "Multi-ETF diversification spreads risk across market segments",
                "Daily timeframe captures intermediate-term trends",
            ],
        },
    },
    # ── 6. Volume Breakout ────────────────────────────────────────────────
    {
        "name": "Volume Breakout",
        "description": (
            "Short-timeframe breakout scanner that triggers on extreme volume spikes "
            "with RSI and ATR confirmation. Designed for 15-minute scalps on any "
            "liquid ticker during volatile sessions."
        ),
        "strategy_type": "breakout",
        "action": "BUY",
        "timeframe": "15m",
        "symbols": ["SPY", "QQQ", "AAPL", "TSLA"],
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.025,
        "position_size_pct": 0.03,
        "conditions": [
            {"indicator": "volume", "operator": ">", "value": 3000000, "params": {}, "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 1.5, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Volume Surge + Volatility",
                "conditions": [
                    {"indicator": "volume", "operator": ">", "value": 3000000, "params": {}, "action": "BUY"},
                    {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "atr", "operator": ">", "value": 1.5, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Identifies breakout opportunities via volume > 3M, RSI > 55 confirming bullish bias, and ATR > 1.5 confirming expanded volatility.",
            "feature_signals": ["Volume spike above 3M", "RSI(14) bullish bias", "ATR(14) volatility expansion"],
            "assumptions": [
                "High volume on 15m bars signals institutional participation",
                "ATR filter ensures sufficient range for profitable scalps",
                "Tight 1% stop-loss required for the short timeframe",
            ],
        },
    },
    # ── 7. Stochastic Reversal ────────────────────────────────────────────
    {
        "name": "Stochastic Reversal",
        "description": (
            "Double-oversold reversal setup using Stochastic K below 20 and RSI below "
            "35 as confirmation. Targets high-beta names like AAPL and TSLA on 4-hour "
            "charts for swing trades."
        ),
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "4H",
        "symbols": ["AAPL", "TSLA"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.06,
        "position_size_pct": 0.04,
        "conditions": [
            {"indicator": "stochastic", "operator": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}, "field": "k", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Double Oversold",
                "conditions": [
                    {"indicator": "stochastic", "operator": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}, "field": "k", "action": "BUY"},
                    {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Enters when both Stochastic %K drops below 20 and RSI(14) below 35 -- dual oversold confirmation for high-probability reversal on AAPL/TSLA.",
            "feature_signals": ["Stochastic %K(14,3) oversold", "RSI(14) oversold cross-confirmation"],
            "assumptions": [
                "Two independent oscillators in oversold territory increases reversal probability",
                "AAPL and TSLA are high-beta names with sharp reversals from oversold levels",
                "4H timeframe balances signal quality with swing trade holding period",
            ],
        },
    },
    # ── 8. Scalping Momentum ─────────────────────────────────────────────
    {
        "name": "Scalping Momentum",
        "description": (
            "Fast 5-minute scalping strategy for SPY that requires RSI momentum, "
            "MACD trend alignment, and sufficient volume. Optimized for quick entries "
            "and exits during high-activity market hours."
        ),
        "strategy_type": "momentum",
        "action": "BUY",
        "timeframe": "5m",
        "symbols": ["SPY"],
        "stop_loss_pct": 0.005,
        "take_profit_pct": 0.012,
        "position_size_pct": 0.03,
        "conditions": [
            {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 1000000, "params": {}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Scalp Entry",
                "conditions": [
                    {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
                    {"indicator": "volume", "operator": ">", "value": 1000000, "params": {}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "5-minute SPY scalper: RSI > 55 for bullish bias, MACD positive for trend, volume > 1M for liquidity. Tight stops and quick targets.",
            "feature_signals": ["RSI(14) bullish momentum", "MACD trend filter", "Volume liquidity check"],
            "assumptions": [
                "SPY on 5m provides enough liquidity for rapid entries/exits",
                "0.5% stop-loss and 1.2% take-profit appropriate for 5-minute moves",
                "Volume filter ensures entries only during active market periods",
            ],
        },
    },
    # ── 9. Swing Trend ────────────────────────────────────────────────────
    {
        "name": "Swing Trend",
        "description": (
            "Multi-day swing strategy that combines an EMA/SMA crossover with RSI "
            "momentum confirmation. Suitable for any large-cap stock on daily charts, "
            "capturing intermediate trends lasting days to weeks."
        ),
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "AAPL", "MSFT", "GOOGL"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "ema", "operator": "crosses_above", "value": 0, "params": {"period": 20}, "compare_to": "sma_50", "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 50, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Trend Initiation",
                "conditions": [
                    {"indicator": "ema", "operator": "crosses_above", "value": 0, "params": {"period": 20}, "compare_to": "sma_50", "action": "BUY"},
                    {"indicator": "rsi", "operator": ">", "value": 50, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Swing entry when EMA(20) crosses above SMA(50) and RSI(14) confirms bullish momentum above 50. Holds for multi-day trends.",
            "feature_signals": ["EMA(20)/SMA(50) crossover", "RSI(14) above neutral 50"],
            "assumptions": [
                "EMA/SMA crossover with RSI confirmation reduces false breakouts",
                "Large-cap names trend cleanly once crossover is confirmed",
                "3% stop and 8% target appropriate for multi-day holding period",
            ],
        },
    },
    # ── 10. ATR Volatility Expansion ──────────────────────────────────────
    {
        "name": "ATR Volatility Expansion",
        "description": (
            "Breakout strategy that triggers when ATR exceeds 2.0, indicating a "
            "volatility expansion phase, combined with RSI momentum above 60. "
            "Designed for hourly SPY and QQQ trading during trending sessions."
        ),
        "strategy_type": "breakout",
        "action": "BUY",
        "timeframe": "1H",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "position_size_pct": 0.04,
        "conditions": [
            {"indicator": "atr", "operator": ">", "value": 2.0, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 60, "params": {"period": 14}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Volatility Breakout",
                "conditions": [
                    {"indicator": "atr", "operator": ">", "value": 2.0, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "rsi", "operator": ">", "value": 60, "params": {"period": 14}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Enters when ATR(14) > 2.0 signals volatility expansion and RSI(14) > 60 confirms bullish direction. Captures trending breakout moves.",
            "feature_signals": ["ATR(14) volatility expansion", "RSI(14) directional momentum"],
            "assumptions": [
                "High ATR indicates the market is making large directional moves",
                "RSI filter ensures we enter in the direction of the breakout",
                "Hourly timeframe on SPY/QQQ provides sufficient volatility signals",
            ],
        },
    },
    # ── 11. Double Confirmation Entry ─────────────────────────────────────
    {
        "name": "Double Confirmation Entry",
        "description": (
            "High-conviction daily strategy requiring four simultaneous signals: "
            "RSI momentum, MACD trend, EMA upslope, and volume confirmation. "
            "Designed for SPY with minimal false signals."
        ),
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY"],
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.06,
        "position_size_pct": 0.05,
        "conditions": [
            {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 20}, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 1500000, "params": {}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Quad Confirmation",
                "conditions": [
                    {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "action": "BUY"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 20}, "action": "BUY"},
                    {"indicator": "volume", "operator": ">", "value": 1500000, "params": {}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Four-signal confluence: RSI > 55, MACD positive, EMA(20) rising, and volume > 1.5M must all align for entry. Maximum conviction, minimum noise.",
            "feature_signals": ["RSI(14) momentum", "MACD histogram positive", "EMA(20) uptrend", "Volume above 1.5M"],
            "assumptions": [
                "Four independent confirmations virtually eliminate false signals",
                "Trade frequency is lower but win rate is significantly higher",
                "SPY on daily charts provides the most reliable multi-signal alignment",
            ],
        },
    },
    # ── 12. Conservative Income ───────────────────────────────────────────
    {
        "name": "Conservative Income",
        "description": (
            "Low-risk income strategy for broad index funds that enters on oversold "
            "conditions at the lower Bollinger Band with volume confirmation. Uses "
            "tight 1% stop-loss and 3% take-profit for consistent small gains."
        ),
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["VTI", "VOO"],
        "stop_loss_pct": 0.01,
        "take_profit_pct": 0.03,
        "position_size_pct": 0.03,
        "conditions": [
            {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "action": "BUY"},
            {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std": 2}, "field": "lower", "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 500000, "params": {}, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "id": "group_1",
                "label": "Conservative Entry",
                "conditions": [
                    {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "action": "BUY"},
                    {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std": 2}, "field": "lower", "action": "BUY"},
                    {"indicator": "volume", "operator": ">", "value": 500000, "params": {}, "action": "BUY"},
                ],
            }
        ],
        "ai_context": {
            "overview": "Conservative dip-buying on VTI/VOO: RSI < 40, price below lower Bollinger Band, and volume > 500K for participation. Tight risk parameters for steady compounding.",
            "feature_signals": ["RSI(14) mild oversold", "Bollinger Band lower touch", "Volume participation check"],
            "assumptions": [
                "VTI and VOO are long-term uptrending -- dips are buying opportunities",
                "1% stop-loss and 3% take-profit maximize win rate over profit per trade",
                "Volume filter avoids entries during illiquid holiday or pre-market periods",
            ],
        },
    },
]


async def seed():
    """Insert all 12 system templates if none exist yet."""
    await init_db()

    async with get_session() as session:
        count = await session.scalar(
            select(func.count()).select_from(StrategyTemplate).where(
                StrategyTemplate.is_system == True  # noqa: E712
            )
        )
        if count and count > 0:
            print(f"Already have {count} system templates -- skipping seed.")
            return

        for tpl_data in SYSTEM_TEMPLATES:
            tpl = StrategyTemplate(
                user_id=SYSTEM_USER_ID,
                is_system=True,
                **tpl_data,
            )
            session.add(tpl)

        await session.flush()
        print(f"Seeded {len(SYSTEM_TEMPLATES)} system strategy templates.")


if __name__ == "__main__":
    asyncio.run(seed())
