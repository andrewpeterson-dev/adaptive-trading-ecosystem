#!/usr/bin/env python3
"""
Deploy GitHub-sourced strategies as paper trading strategies for the default user.

1. Seeds any new system templates (including the 5 GitHub strategies)
2. Creates StrategyTemplate + StrategyInstance (paper mode) for each GitHub strategy
3. Runs validation on each strategy before saving
4. Reports results

Safe to re-run — checks for existing strategies by name.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from db.database import get_session
from db.models import StrategyTemplate, StrategyInstance, TradingModeEnum
from services.strategy_validator import validate_strategy_config
from services.diagnostics import StrategyDiagnostics

import os
DEFAULT_USER_ID = int(os.environ.get("DEPLOY_USER_ID", "2"))

# The 5 GitHub-sourced strategies to deploy as paper trading strategies
GITHUB_STRATEGIES = [
    {
        "name": "[NostalgiaForInfinity] Multi-Indicator Trend",
        "description": "Multi-indicator trend confirmation from github.com/iterativv/NostalgiaForInfinity (2.9k stars). 4-indicator alignment: EMA crossover + RSI trend zone + MACD momentum + EMA(200) filter.",
        "strategy_type": "custom",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "AAPL"],
        "stop_loss_pct": 0.03,
        "take_profit_pct": 0.08,
        "position_size_pct": 0.05,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "cooldown_bars": 3,
        "max_trades_per_day": 2,
        "max_exposure_pct": 0.15,
        "max_loss_pct": 0.05,
        "conditions": [
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 12}, "field": None, "compare_to": "ema_26", "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "field": None, "compare_to": None, "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 12}, "compare_to": "ema_26", "logic": "AND", "signal": "EMA(12) > EMA(26)"},
                    {"indicator": "rsi", "operator": ">", "value": 40, "params": {"period": 14}, "logic": "AND", "signal": "RSI > 40"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "logic": "AND", "signal": "MACD histogram > 0"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 200}, "logic": "AND", "signal": "Price > EMA(200)"},
                ]
            }
        ],
        "ai_context": {"source": "https://github.com/iterativv/NostalgiaForInfinity"},
    },
    {
        "name": "[freqAI-LSTM] Multi-Factor Momentum",
        "description": "Multi-factor momentum scoring from github.com/Netanelshoshan/freqAI-LSTM. Simultaneous RSI momentum flip + MACD crossover + volume surge + EMA alignment.",
        "strategy_type": "custom",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "NVDA"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.07,
        "position_size_pct": 0.05,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "cooldown_bars": 3,
        "max_trades_per_day": 2,
        "max_exposure_pct": 0.15,
        "max_loss_pct": 0.05,
        "conditions": [
            {"indicator": "rsi", "operator": "crosses_above", "value": 50, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
            {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 9}, "field": None, "compare_to": "ema_21", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "rsi", "operator": "crosses_above", "value": 50, "params": {"period": 14}, "logic": "AND", "signal": "RSI crosses above 50"},
                    {"indicator": "macd", "operator": "crosses_above", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "macd", "compare_to": "macd.signal", "logic": "AND", "signal": "MACD crosses above signal"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume > SMA(20)"},
                    {"indicator": "ema", "operator": ">", "value": 0, "params": {"period": 9}, "compare_to": "ema_21", "logic": "AND", "signal": "EMA(9) > EMA(21)"},
                ]
            }
        ],
        "ai_context": {"source": "https://github.com/Netanelshoshan/freqAI-LSTM"},
    },
    {
        "name": "[Momentum Transformer] Regime Trend",
        "description": "Trend-following with regime detection from github.com/kieranjwood/trading-momentum-transformer (arXiv:2112.08534). SMA golden cross + RSI momentum + MACD acceleration + ATR regime shift.",
        "strategy_type": "custom",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ"],
        "stop_loss_pct": 0.04,
        "take_profit_pct": 0.12,
        "position_size_pct": 0.05,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "cooldown_bars": 5,
        "max_trades_per_day": 1,
        "max_exposure_pct": 0.10,
        "max_loss_pct": 0.05,
        "conditions": [
            {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "field": None, "compare_to": "sma_200", "action": "BUY"},
            {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "compare_to": None, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "sma", "operator": ">", "value": 0, "params": {"period": 50}, "compare_to": "sma_200", "logic": "AND", "signal": "SMA(50) > SMA(200)"},
                    {"indicator": "rsi", "operator": ">", "value": 55, "params": {"period": 14}, "logic": "AND", "signal": "RSI > 55"},
                    {"indicator": "macd", "operator": ">", "value": 0, "params": {"fast": 12, "slow": 26, "signal": 9}, "field": "histogram", "logic": "AND", "signal": "MACD histogram > 0"},
                    {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding"},
                ]
            }
        ],
        "ai_context": {"source": "https://github.com/kieranjwood/trading-momentum-transformer"},
    },
    {
        "name": "[Awesome Systematic] Volatility Mean Reversion",
        "description": "Volatility-momentum mean reversion from github.com/paperswithbacktest/awesome-systematic-trading. BB oversold + Stochastic reversal + RSI confirmation + volume.",
        "strategy_type": "custom",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "IWM", "QQQ"],
        "stop_loss_pct": 0.025,
        "take_profit_pct": 0.06,
        "position_size_pct": 0.05,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "cooldown_bars": 2,
        "max_trades_per_day": 2,
        "max_exposure_pct": 0.15,
        "max_loss_pct": 0.05,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": "<", "value": 0.2, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "action": "BUY"},
            {"indicator": "stochastic", "operator": "crosses_above", "value": 0, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": "stochastic.d", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": "<", "value": 0.2, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "logic": "AND", "signal": "BB %B < 0.2"},
                    {"indicator": "stochastic", "operator": "crosses_above", "value": 0, "params": {"k_period": 14, "d_period": 3}, "field": "k", "compare_to": "stochastic.d", "logic": "AND", "signal": "Stochastic %K crosses %D"},
                    {"indicator": "rsi", "operator": "<", "value": 40, "params": {"period": 14}, "logic": "AND", "signal": "RSI < 40"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume > SMA(20)"},
                ]
            }
        ],
        "ai_context": {"source": "https://github.com/paperswithbacktest/awesome-systematic-trading"},
    },
    {
        "name": "[je-suis-tm/Quant] Dual Thrust Breakout",
        "description": "Volatility breakout from github.com/je-suis-tm/quant-trading (9.4k stars). Price breaks above upper BB + volume surge + RSI not extreme + ATR expanding.",
        "strategy_type": "custom",
        "action": "BUY",
        "timeframe": "1D",
        "symbols": ["SPY", "QQQ", "AAPL"],
        "stop_loss_pct": 0.035,
        "take_profit_pct": 0.10,
        "position_size_pct": 0.05,
        "commission_pct": 0.001,
        "slippage_pct": 0.0005,
        "cooldown_bars": 3,
        "max_trades_per_day": 2,
        "max_exposure_pct": 0.15,
        "max_loss_pct": 0.05,
        "conditions": [
            {"indicator": "bollinger_bands", "operator": ">", "value": 1, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "compare_to": None, "action": "BUY"},
            {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "field": None, "compare_to": "sma_20", "action": "BUY"},
            {"indicator": "rsi", "operator": "<", "value": 75, "params": {"period": 14}, "field": None, "compare_to": None, "action": "BUY"},
            {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "field": None, "compare_to": "atr_prev", "action": "BUY"},
        ],
        "condition_groups": [
            {
                "conditions": [
                    {"indicator": "bollinger_bands", "operator": ">", "value": 1, "params": {"period": 20, "std_dev": 2}, "field": "pct_b", "logic": "AND", "signal": "BB %B > 1.0 — breakout above upper band"},
                    {"indicator": "volume", "operator": ">", "value": 0, "params": {}, "compare_to": "sma_20", "logic": "AND", "signal": "Volume > SMA(20)"},
                    {"indicator": "rsi", "operator": "<", "value": 75, "params": {"period": 14}, "logic": "AND", "signal": "RSI < 75"},
                    {"indicator": "atr", "operator": ">", "value": 0, "params": {"period": 14}, "compare_to": "atr_prev", "logic": "AND", "signal": "ATR expanding"},
                ]
            }
        ],
        "ai_context": {"source": "https://github.com/je-suis-tm/quant-trading"},
    },
]


async def validate_and_report(strategy: dict) -> tuple[bool, list, list]:
    """Run validation on a strategy config and return results."""
    config = {
        "conditions": strategy["conditions"],
        "condition_groups": strategy.get("condition_groups", []),
        "action": strategy["action"],
        "timeframe": strategy["timeframe"],
        "symbols": strategy["symbols"],
        "stop_loss_pct": strategy["stop_loss_pct"],
        "take_profit_pct": strategy["take_profit_pct"],
        "position_size_pct": strategy.get("position_size_pct", 0.05),
    }
    return validate_strategy_config(config)


async def deploy_github_strategies():
    """Deploy the 5 GitHub strategies as paper trading strategies."""

    # Step 1: Seed system templates first
    print("=" * 60)
    print("Step 1: Seeding system templates...")
    print("=" * 60)
    from scripts.seed_templates import seed_templates
    await seed_templates()

    # Step 2: Validate all strategies before deploying
    print("\n" + "=" * 60)
    print("Step 2: Validating all 5 GitHub strategies...")
    print("=" * 60)

    all_valid = True
    for strat in GITHUB_STRATEGIES:
        is_valid, errors, warnings = await validate_and_report(strat)
        status = "PASS" if is_valid else "FAIL"
        print(f"\n  [{status}] {strat['name']}")
        if errors:
            print(f"    Errors: {errors}")
            all_valid = False
        if warnings:
            print(f"    Warnings: {warnings}")

    if not all_valid:
        print("\nSome strategies failed validation. Aborting deployment.")
        return

    print("\nAll strategies passed validation.")

    # Step 3: Deploy as paper trading strategies
    print("\n" + "=" * 60)
    print(f"Step 3: Deploying strategies for paper trading (user_id={DEFAULT_USER_ID})...")
    print("=" * 60)

    async with get_session() as session:
        # Check existing strategies for this user
        result = await session.execute(
            select(StrategyTemplate).where(
                StrategyTemplate.user_id == DEFAULT_USER_ID,
                StrategyTemplate.name.in_([s["name"] for s in GITHUB_STRATEGIES]),
            )
        )
        existing = {t.name for t in result.scalars().all()}

        created = 0
        skipped = 0

        for strat in GITHUB_STRATEGIES:
            if strat["name"] in existing:
                print(f"  [SKIP] {strat['name']} — already exists")
                skipped += 1
                continue

            # Run diagnostics
            conditions = strat["conditions"]
            params = {}
            for c in conditions:
                ind = c["indicator"]
                p = c.get("params", {})
                params[ind] = p

            report = StrategyDiagnostics.run_all(
                conditions,
                params,
                has_stop_loss=bool(strat.get("stop_loss_pct")),
                has_take_profit=bool(strat.get("take_profit_pct")),
            )

            # Create StrategyTemplate
            template = StrategyTemplate(
                user_id=DEFAULT_USER_ID,
                name=strat["name"],
                description=strat["description"],
                strategy_type=strat.get("strategy_type", "custom"),
                action=strat["action"],
                timeframe=strat["timeframe"],
                symbols=strat["symbols"],
                stop_loss_pct=strat["stop_loss_pct"],
                take_profit_pct=strat["take_profit_pct"],
                conditions=conditions,
                condition_groups=strat.get("condition_groups", []),
                commission_pct=strat.get("commission_pct", 0.001),
                slippage_pct=strat.get("slippage_pct", 0.0005),
                cooldown_bars=strat.get("cooldown_bars", 0),
                max_trades_per_day=strat.get("max_trades_per_day", 0),
                max_exposure_pct=strat.get("max_exposure_pct", 1.0),
                max_loss_pct=strat.get("max_loss_pct", 0.0),
                diagnostics=report.to_dict(),
                ai_context=strat.get("ai_context", {}),
                is_system=False,
            )
            session.add(template)
            await session.flush()

            # Create StrategyInstance (paper mode)
            instance = StrategyInstance(
                template_id=template.id,
                user_id=DEFAULT_USER_ID,
                mode=TradingModeEnum.PAPER,
                is_active=True,
                position_size_pct=strat.get("position_size_pct", 0.05),
                nickname=strat["name"],
            )
            session.add(instance)
            await session.flush()

            print(f"  [CREATED] {strat['name']}")
            print(f"    Template ID: {template.id}, Instance ID: {instance.id}")
            print(f"    Mode: PAPER, Position size: {strat.get('position_size_pct', 0.05)*100}%")
            print(f"    Diagnostics score: {report.score}/100")
            created += 1

    print(f"\n{'=' * 60}")
    print(f"Deployment complete: {created} created, {skipped} skipped")
    print(f"{'=' * 60}")

    if created > 0:
        print("\nStrategies are now active in PAPER mode.")
        print("They will be evaluated by the BotRunner on the next cycle.")
        print("View them at: http://localhost:3000/strategies")


if __name__ == "__main__":
    asyncio.run(deploy_github_strategies())
