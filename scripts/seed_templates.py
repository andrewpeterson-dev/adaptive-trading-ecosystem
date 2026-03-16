#!/usr/bin/env python3
"""
Seed the strategy_templates table with built-in system templates.

Safe to re-run — checks for existing system templates by name before inserting.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.database import get_session
from db.models import StrategyTemplate

SYSTEM_USER_ID = 1

SYSTEM_TEMPLATES = [
    {
        "name": "RSI Oversold Bounce",
        "description": "Buy when RSI dips below 30 on above-average volume — a classic momentum reversal setup.",
        "strategy_type": "momentum",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "conditions": [
            {"indicator": "rsi", "operator": "<", "value": 30, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "rsi", "operator": "<", "value": 30, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI below 30 (oversold)"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day SMA"},
                ]
            }
        ],
        "ai_context": {
            "name": "RSI Oversold Bounce",
            "description": "Buy when RSI dips below 30 on above-average volume — a classic momentum reversal setup.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ"],
            "stopLossPct": 3,
            "takeProfitPct": 8,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Targets short-term oversold bounces. RSI < 30 signals exhausted selling pressure; volume confirmation filters out false bottoms.",
            "featureSignals": ["RSI(14) < 30", "Volume > SMA(20)"],
            "entryConditions": [
                {"indicator": "rsi", "operator": "<", "value": 30, "params": {"period": 14}, "logic": "AND", "signal": "RSI below 30 (oversold)"},
                {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day SMA"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 3, "description": "Exit if price drops 3% from entry"},
                {"type": "take_profit", "value": 8, "description": "Exit if price rises 8% from entry"},
            ],
        },
    },
    {
        "name": "Bollinger Squeeze",
        "description": "Mean-reversion play: buy when price touches the lower Bollinger Band while ATR is expanding.",
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.06,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std_dev": 2}, "field": "lower", "compare_to": None, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std_dev": 2}, "field": "lower", "compare_to": None, "logic": "AND", "signal": "Price below lower Bollinger Band"},
                    {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding (volatility increasing)"},
                ]
            }
        ],
        "ai_context": {
            "name": "Bollinger Squeeze",
            "description": "Mean-reversion play: buy when price touches the lower Bollinger Band while ATR is expanding.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY"],
            "stopLossPct": 2.5,
            "takeProfitPct": 6,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Captures mean-reversion snaps after price stretches below the lower band. ATR expansion confirms the move is real, not a low-vol drift.",
            "featureSignals": ["Price < Lower BB(20,2)", "ATR(14) expanding"],
            "entryConditions": [
                {"indicator": "bollinger_bands", "operator": "<", "value": 0, "params": {"period": 20, "std_dev": 2}, "field": "lower", "logic": "AND", "signal": "Price below lower Bollinger Band"},
                {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding (volatility increasing)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 2.5, "description": "Exit if price drops 2.5% from entry"},
                {"type": "take_profit", "value": 6, "description": "Exit if price rises 6% from entry"},
            ],
        },
    },
    {
        "name": "MACD Crossover",
        "description": "Momentum entry when MACD crosses above the signal line with price above the 200-day EMA.",
        "strategy_type": "momentum",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["AAPL", "MSFT", "NVDA"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.07,
        "conditions": [
            {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "field": None, "compare_to": None, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "logic": "AND", "signal": "MACD crosses above signal line"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "field": None, "compare_to": None, "logic": "AND", "signal": "Price above EMA(200)"},
                ]
            }
        ],
        "ai_context": {
            "name": "MACD Crossover",
            "description": "Momentum entry when MACD crosses above the signal line with price above the 200-day EMA.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["AAPL", "MSFT", "NVDA"],
            "stopLossPct": 3,
            "takeProfitPct": 7,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Classic dual-confirmation momentum strategy. MACD crossover spots trend acceleration; the EMA(200) filter keeps you on the right side of the long-term trend.",
            "featureSignals": ["MACD crosses above Signal", "Price > EMA(200)"],
            "entryConditions": [
                {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "logic": "AND", "signal": "MACD crosses above signal line"},
                {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "logic": "AND", "signal": "Price above EMA(200)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 3, "description": "Exit if price drops 3% from entry"},
                {"type": "take_profit", "value": 7, "description": "Exit if price rises 7% from entry"},
            ],
        },
    },
    {
        "name": "Volume Breakout",
        "description": "Breakout entry on a volume surge (2x average) with price above the 50-day SMA.",
        "strategy_type": "breakout",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.10,
        "conditions": [
            {"indicator": "volume", "operator": ">", "value": 2, "params": {"period": 20}, "field": None, "compare_to": "volume_sma_20", "action": "BUY"},
            {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "field": None, "compare_to": None, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "volume", "operator": ">", "value": 2, "params": {"period": 20}, "field": None, "compare_to": "volume_sma_20", "logic": "AND", "signal": "Volume > 2x SMA(20)"},
                    {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "field": None, "compare_to": None, "logic": "AND", "signal": "Price above SMA(50)"},
                ]
            }
        ],
        "ai_context": {
            "name": "Volume Breakout",
            "description": "Breakout entry on a volume surge (2x average) with price above the 50-day SMA.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ"],
            "stopLossPct": 4,
            "takeProfitPct": 10,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "High-conviction breakout filter. A 2x volume spike shows institutional participation; the SMA(50) guard avoids buying into downtrends.",
            "featureSignals": ["Volume > 2x SMA(20)", "Price > SMA(50)"],
            "entryConditions": [
                {"indicator": "volume", "operator": ">", "value": 2, "params": {"period": 20}, "compare_to": "volume_sma_20", "logic": "AND", "signal": "Volume > 2x SMA(20)"},
                {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "logic": "AND", "signal": "Price above SMA(50)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 4, "description": "Exit if price drops 4% from entry"},
                {"type": "take_profit", "value": 10, "description": "Exit if price rises 10% from entry"},
            ],
        },
    },
    {
        "name": "Golden Cross",
        "description": "Trend-following entry when the 50-day SMA crosses above the 200-day SMA.",
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY"],
        "stop_loss_pct": 0.05,
        "take_profit_pct": 0.15,
        "conditions": [
            {"indicator": "sma", "operator": "crosses_above", "value": 0, "params": {"period": 50}, "field": None, "compare_to": "sma_200", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "sma", "operator": "crosses_above", "value": 0, "params": {"period": 50}, "field": None, "compare_to": "sma_200", "logic": "AND", "signal": "SMA(50) crosses above SMA(200)"},
                ]
            }
        ],
        "ai_context": {
            "name": "Golden Cross",
            "description": "Trend-following entry when the 50-day SMA crosses above the 200-day SMA.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY"],
            "stopLossPct": 5,
            "takeProfitPct": 15,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "The golden cross is one of the most widely followed long-term trend signals. When the 50-day SMA crosses above the 200-day SMA it often marks the start of a sustained uptrend.",
            "featureSignals": ["SMA(50) crosses above SMA(200)"],
            "entryConditions": [
                {"indicator": "sma", "operator": "crosses_above", "value": 0, "params": {"period": 50}, "compare_to": "sma_200", "logic": "AND", "signal": "SMA(50) crosses above SMA(200)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 5, "description": "Exit if price drops 5% from entry"},
                {"type": "take_profit", "value": 15, "description": "Exit if price rises 15% from entry"},
            ],
        },
    },
    {
        "name": "Stochastic Reversal",
        "description": "Mean-reversion entry when Stochastic %K drops below 20 and RSI confirms oversold below 35.",
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "IWM"],
        "stop_loss_pct": 0.02,
        "take_profit_pct": 0.05,
        "conditions": [
            {"indicator": "stochastic", "operator": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": None, "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "stochastic", "operator": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": None, "logic": "AND", "signal": "Stochastic %K below 20"},
                    {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI below 35 (confirming oversold)"},
                ]
            }
        ],
        "ai_context": {
            "name": "Stochastic Reversal",
            "description": "Mean-reversion entry when Stochastic %K drops below 20 and RSI confirms oversold below 35.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "IWM"],
            "stopLossPct": 2,
            "takeProfitPct": 5,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Dual-oscillator oversold filter. Stochastic %K < 20 catches the fastest-moving reversals; RSI < 35 adds a second confirmation layer to reduce false signals.",
            "featureSignals": ["Stoch %K(14) < 20", "RSI(14) < 35"],
            "entryConditions": [
                {"indicator": "stochastic", "operator": "<", "value": 20, "params": {"k_period": 14, "d_period": 3}, "field": "k", "logic": "AND", "signal": "Stochastic %K below 20"},
                {"indicator": "rsi", "operator": "<", "value": 35, "params": {"period": 14}, "logic": "AND", "signal": "RSI below 35 (confirming oversold)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 2, "description": "Exit if price drops 2% from entry"},
                {"type": "take_profit", "value": 5, "description": "Exit if price rises 5% from entry"},
            ],
        },
    },
]


async def seed_templates():
    """Insert system templates if they don't already exist. Idempotent."""
    async with get_session() as db:
        result = await db.execute(
            select(StrategyTemplate).where(StrategyTemplate.is_system == True)  # noqa: E712
        )
        existing = {t.name for t in result.scalars().all()}

        added = 0
        for tpl_data in SYSTEM_TEMPLATES:
            if tpl_data["name"] in existing:
                continue
            template = StrategyTemplate(
                user_id=SYSTEM_USER_ID,
                name=tpl_data["name"],
                description=tpl_data["description"],
                strategy_type=tpl_data["strategy_type"],
                action=tpl_data["action"],
                timeframe=tpl_data["timeframe"],
                symbols=tpl_data["symbols"],
                stop_loss_pct=tpl_data["stop_loss_pct"],
                take_profit_pct=tpl_data["take_profit_pct"],
                conditions=tpl_data["conditions"],
                condition_groups=tpl_data["condition_groups"],
                ai_context=tpl_data["ai_context"],
                is_system=True,
            )
            db.add(template)
            added += 1

    if added:
        print(f"System templates: added {added}.")
    else:
        print("System templates: already up to date.")


if __name__ == "__main__":
    asyncio.run(seed_templates())
