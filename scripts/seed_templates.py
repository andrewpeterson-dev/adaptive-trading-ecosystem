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
    # ── GitHub-Sourced Strategies ──────────────────────────────────────────
    {
        "name": "[NostalgiaForInfinity] Multi-Indicator Trend",
        "description": "Multi-indicator trend confirmation inspired by iterativv/NostalgiaForInfinity (2.9k stars). Aligns short-term EMA crossover, RSI trend zone, MACD momentum, and long-term EMA filter.",
        "strategy_type": "momentum",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "AAPL"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "conditions": [
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 12}, "field": None, "compare_to": "ema_26", "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "field": None, "compare_to": None, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 12}, "field": None, "compare_to": "ema_26", "logic": "AND", "signal": "EMA(12) above EMA(26) — short-term uptrend"},
                    {"indicator": "rsi", "operator": ">", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI above 40 — in trend zone, not oversold"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "logic": "AND", "signal": "MACD histogram positive — momentum accelerating"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "field": None, "compare_to": None, "logic": "AND", "signal": "Price above EMA(200) — long-term uptrend intact"},
                ]
            }
        ],
        "ai_context": {
            "name": "[NostalgiaForInfinity] Multi-Indicator Trend",
            "description": "Multi-indicator trend confirmation inspired by iterativv/NostalgiaForInfinity (2.9k stars). Aligns short-term EMA crossover, RSI trend zone, MACD momentum, and long-term EMA filter.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ", "AAPL"],
            "stopLossPct": 3,
            "takeProfitPct": 8,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Adapted from NostalgiaForInfinity's multi-timeframe alignment approach. Uses 4 indicators across different timeframes to confirm a strong trend before entering. The EMA(12)/EMA(26) crossover catches the trend early, RSI(40+) ensures we're not buying into weakness, MACD histogram confirms acceleration, and EMA(200) keeps us on the right side of the macro trend.",
            "featureSignals": ["EMA(12) > EMA(26)", "RSI(14) > 40", "MACD Histogram > 0", "Price > EMA(200)"],
            "entryConditions": [
                {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 12}, "compare_to": "ema_26", "logic": "AND", "signal": "EMA(12) above EMA(26) — short-term uptrend"},
                {"indicator": "rsi", "operator": ">", "value": 40, "params": {"period": 14}, "logic": "AND", "signal": "RSI above 40 — in trend zone"},
                {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "logic": "AND", "signal": "MACD histogram positive"},
                {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "logic": "AND", "signal": "Price above EMA(200)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 3, "description": "Exit if price drops 3% from entry"},
                {"type": "take_profit", "value": 8, "description": "Exit if price rises 8% from entry"},
            ],
            "source": "https://github.com/iterativv/NostalgiaForInfinity",
        },
    },
    {
        "name": "[freqAI-LSTM] Multi-Factor Momentum",
        "description": "Multi-factor momentum scoring inspired by Netanelshoshan/freqAI-LSTM. Combines RSI momentum flip, MACD crossover, volume surge, and short-term EMA alignment for high-conviction entries.",
        "strategy_type": "momentum",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "NVDA"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.07,
        "conditions": [
            {"indicator": "rsi", "operator": "crosses_above", "value": 50, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 9}, "field": None, "compare_to": "ema_21", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "rsi", "operator": "crosses_above", "value": 50, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI crosses above 50 — momentum flips bullish"},
                    {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "logic": "AND", "signal": "MACD crosses above signal — bullish crossover"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day average — institutional participation"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 9}, "field": None, "compare_to": "ema_21", "logic": "AND", "signal": "EMA(9) above EMA(21) — short-term trend up"},
                ]
            }
        ],
        "ai_context": {
            "name": "[freqAI-LSTM] Multi-Factor Momentum",
            "description": "Multi-factor momentum scoring inspired by Netanelshoshan/freqAI-LSTM. Combines RSI momentum flip, MACD crossover, volume surge, and short-term EMA alignment.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ", "NVDA"],
            "stopLossPct": 2.5,
            "takeProfitPct": 7,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Adapted from freqAI-LSTM's multi-feature scoring approach. Instead of an ML model, we use 4 independent momentum signals that must all align simultaneously — effectively a hand-crafted 'score' that approximates the LSTM's learned features. RSI crossing 50 catches the momentum regime shift, MACD crossover confirms trend acceleration, volume validates institutional interest, and EMA(9)/EMA(21) confirms the short-term structure.",
            "featureSignals": ["RSI(14) crosses 50", "MACD > Signal", "Volume > SMA(20)", "EMA(9) > EMA(21)"],
            "entryConditions": [
                {"indicator": "rsi", "operator": "crosses_above", "value": 50, "params": {"period": 14}, "logic": "AND", "signal": "RSI crosses above 50"},
                {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "logic": "AND", "signal": "MACD crosses above signal"},
                {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day average"},
                {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 9}, "compare_to": "ema_21", "logic": "AND", "signal": "EMA(9) above EMA(21)"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 2.5, "description": "Exit if price drops 2.5% from entry"},
                {"type": "take_profit", "value": 7, "description": "Exit if price rises 7% from entry"},
            ],
            "source": "https://github.com/Netanelshoshan/freqAI-LSTM",
        },
    },
    {
        "name": "[Momentum Transformer] Regime Trend",
        "description": "Trend-following with regime detection inspired by kieranjwood/trading-momentum-transformer (arXiv:2112.08534). Uses SMA golden cross, RSI momentum confirmation, positive MACD, and expanding ATR to identify trend acceleration regimes.",
        "strategy_type": "trend",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.12,
        "conditions": [
            {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "field": None, "compare_to": "sma_200", "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "field": None, "compare_to": "sma_200", "logic": "AND", "signal": "SMA(50) above SMA(200) — macro uptrend confirmed"},
                    {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI above 55 — momentum favoring bulls"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "logic": "AND", "signal": "MACD histogram positive — trend accelerating"},
                    {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding — volatility regime shift (momentum regime)"},
                ]
            }
        ],
        "ai_context": {
            "name": "[Momentum Transformer] Regime Trend",
            "description": "Trend-following with regime detection inspired by kieranjwood/trading-momentum-transformer. The paper uses LSTM+attention+changepoint detection; this adaptation uses ATR expansion as a regime proxy.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ"],
            "stopLossPct": 4,
            "takeProfitPct": 12,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Adapted from the Momentum Transformer paper (arXiv:2112.08534) which achieved +33% Sharpe improvement via attention-based momentum with online changepoint detection. This rule-based version uses: SMA(50)>SMA(200) as the macro trend filter (replaces learned trend signal), RSI>55 for momentum confirmation, MACD histogram for acceleration, and ATR expansion as a proxy for the paper's changepoint detection — identifying regime shifts from low-vol consolidation to high-vol trending.",
            "featureSignals": ["SMA(50) > SMA(200)", "RSI(14) > 55", "MACD Histogram > 0", "ATR(14) expanding"],
            "entryConditions": [
                {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "compare_to": "sma_200", "logic": "AND", "signal": "SMA(50) above SMA(200)"},
                {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "logic": "AND", "signal": "RSI above 55"},
                {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "logic": "AND", "signal": "MACD histogram positive"},
                {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 4, "description": "Exit if price drops 4% from entry"},
                {"type": "take_profit", "value": 12, "description": "Exit if price rises 12% from entry"},
            ],
            "source": "https://github.com/kieranjwood/trading-momentum-transformer",
        },
    },
    {
        "name": "[Awesome Systematic] Volatility Mean Reversion",
        "description": "Volatility-momentum mean reversion from paperswithbacktest/awesome-systematic-trading. Buys when price reaches lower Bollinger Band with Stochastic reversal signal, RSI oversold, and volume confirmation.",
        "strategy_type": "mean_reversion",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "IWM", "QQQ"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.06,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": "<", "value": 0.2, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "action": "BUY"},
            {"indicator": "stochastic", "operator": "crosses_above", "value": 0, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": "stochastic.d", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": "<", "value": 0.2, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "logic": "AND", "signal": "BB %B below 0.2 — price near lower band"},
                    {"indicator": "stochastic", "operator": "crosses_above", "value": 0, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": "stochastic.d", "logic": "AND", "signal": "Stochastic %K crosses above %D — momentum reversing up"},
                    {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI below 40 — oversold confirmation"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above average — not a low-vol drift"},
                ]
            }
        ],
        "ai_context": {
            "name": "[Awesome Systematic] Volatility Mean Reversion",
            "description": "Volatility-momentum mean reversion from paperswithbacktest/awesome-systematic-trading. Combines Bollinger Band proximity, Stochastic reversal, RSI oversold, and volume confirmation.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "IWM", "QQQ"],
            "stopLossPct": 2.5,
            "takeProfitPct": 6,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Adapted from the 'Momentum and Reversal Combined with Volatility Effect' paper in the awesome-systematic-trading collection. The original uses cross-sectional factor ranking; this adaptation captures the same insight (high-volatility stocks that have been beaten down tend to revert) using: BB %B < 0.2 identifies price stretched to the lower band, Stochastic %K crossing %D catches the exact reversal moment, RSI < 40 confirms oversold conditions, and above-average volume ensures the reversal has institutional backing.",
            "featureSignals": ["BB %B < 0.2", "Stoch %K crosses %D", "RSI(14) < 40", "Volume > SMA(20)"],
            "entryConditions": [
                {"indicator": "bollinger_bands", "operator": "<", "value": 0.2, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "logic": "AND", "signal": "BB %B below 0.2"},
                {"indicator": "stochastic", "operator": "crosses_above", "value": 0, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": "stochastic.d", "logic": "AND", "signal": "Stochastic reversal"},
                {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "logic": "AND", "signal": "RSI below 40"},
                {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above average"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 2.5, "description": "Exit if price drops 2.5% from entry"},
                {"type": "take_profit", "value": 6, "description": "Exit if price rises 6% from entry"},
            ],
            "source": "https://github.com/paperswithbacktest/awesome-systematic-trading",
        },
    },
    {
        "name": "[je-suis-tm/Quant] Dual Thrust Breakout",
        "description": "Volatility breakout adapted from je-suis-tm/quant-trading (9.4k stars). Enters when price breaks above the upper Bollinger Band on a volume surge with expanding ATR and RSI not yet at extremes.",
        "strategy_type": "breakout",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "AAPL"],
        "stop_loss_pct": 0.035,
        "take_profit_pct": 0.10,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": ">", "value": 1, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 75, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": ">", "value": 1, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "logic": "AND", "signal": "BB %B above 1.0 — price breaking above upper band"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day average — confirming breakout"},
                    {"indicator": "rsi", "operator": "<", "value": 75, "params": {"period": 14}, "field": None, "compare_to": None, "logic": "AND", "signal": "RSI below 75 — room to run, not yet at extreme overbought"},
                    {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding — volatility confirming breakout"},
                ]
            }
        ],
        "ai_context": {
            "name": "[je-suis-tm/Quant] Dual Thrust Breakout",
            "description": "Volatility breakout adapted from je-suis-tm/quant-trading (9.4k stars). The original Dual Thrust uses opening range bands; this adaptation uses Bollinger Bands as dynamic range bands.",
            "action": "BUY",
            "timeframe": "1D",
            "symbols": ["SPY", "QQQ", "AAPL"],
            "stopLossPct": 3.5,
            "takeProfitPct": 10,
            "positionPct": 5,
            "strategyType": "system",
            "overview": "Adapted from the Dual Thrust strategy in je-suis-tm/quant-trading, one of the most popular quantitative trading repos on GitHub (9.4k stars). The original uses dynamic open+range bands for intraday breakouts; this daily-timeframe adaptation uses Bollinger Bands as the dynamic range. BB %B > 1.0 catches the price breaking above the upper band (analogous to upper thrust), volume confirmation filters false breakouts, RSI < 75 ensures we're not buying at exhaustion, and ATR expansion confirms the volatility regime supports continuation.",
            "featureSignals": ["BB %B > 1.0", "Volume > SMA(20)", "RSI(14) < 75", "ATR(14) expanding"],
            "entryConditions": [
                {"indicator": "bollinger_bands", "operator": ">", "value": 1, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "logic": "AND", "signal": "BB %B above 1.0 — breakout"},
                {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume above 20-day average"},
                {"indicator": "rsi", "operator": "<", "value": 75, "params": {"period": 14}, "logic": "AND", "signal": "RSI below 75 — room to run"},
                {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding"},
            ],
            "exitConditions": [
                {"type": "stop_loss", "value": 3.5, "description": "Exit if price drops 3.5% from entry"},
                {"type": "take_profit", "value": 10, "description": "Exit if price rises 10% from entry"},
            ],
            "source": "https://github.com/je-suis-tm/quant-trading",
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
