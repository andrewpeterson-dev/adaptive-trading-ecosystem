#!/usr/bin/env python3
"""Seed the database with example trading data for demo purposes."""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from config.settings import get_settings
from db.database import Base
from db.models import (
    CapitalAllocation,
    MarketRegime,
    MarketRegimeRecord,
    ModelPerformance,
    PortfolioSnapshot,
    RiskEvent,
    RiskEventType,
    Trade,
    TradeDirection,
    TradeStatus,
    TradingModeEnum,
    TradingModel,
)

settings = get_settings()
engine = create_engine(settings.database_url_sync)


def seed():
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        # Check if data already exists
        if session.query(TradingModel).first():
            print("Data already seeded. Skipping.")
            return

        now = datetime.utcnow()

        # -- Trading models --
        momentum = TradingModel(
            name="momentum_v1",
            model_type="momentum",
            version="1.2.0",
            is_active=True,
            parameters={"lookback": 20, "threshold": 0.02},
        )
        mean_rev = TradingModel(
            name="mean_reversion_v1",
            model_type="mean_reversion",
            version="1.0.0",
            is_active=True,
            parameters={"window": 50, "z_score_threshold": 2.0},
        )
        ml_model = TradingModel(
            name="xgboost_ensemble",
            model_type="ml_ensemble",
            version="2.1.0",
            is_active=True,
            parameters={"n_estimators": 500, "max_depth": 6},
        )
        session.add_all([momentum, mean_rev, ml_model])
        session.flush()

        # -- Trades --
        trades = [
            Trade(
                model_id=momentum.id, symbol="AAPL", direction=TradeDirection.LONG,
                quantity=100, entry_price=185.50, exit_price=192.30,
                pnl=680.0, pnl_pct=3.66, status=TradeStatus.FILLED,
                mode=TradingModeEnum.PAPER,
                entry_time=now - timedelta(days=5), exit_time=now - timedelta(days=3),
            ),
            Trade(
                model_id=mean_rev.id, symbol="TSLA", direction=TradeDirection.SHORT,
                quantity=50, entry_price=245.00, exit_price=238.20,
                pnl=340.0, pnl_pct=2.78, status=TradeStatus.FILLED,
                mode=TradingModeEnum.PAPER,
                entry_time=now - timedelta(days=4), exit_time=now - timedelta(days=2),
            ),
            Trade(
                model_id=ml_model.id, symbol="NVDA", direction=TradeDirection.LONG,
                quantity=30, entry_price=720.00, status=TradeStatus.FILLED,
                mode=TradingModeEnum.PAPER,
                entry_time=now - timedelta(days=1),
            ),
        ]
        session.add_all(trades)

        # -- Model performance --
        for model, sharpe, wr in [(momentum, 1.85, 0.62), (mean_rev, 1.42, 0.58), (ml_model, 2.10, 0.65)]:
            session.add(ModelPerformance(
                model_id=model.id, sharpe_ratio=sharpe, sortino_ratio=sharpe * 1.1,
                win_rate=wr, profit_factor=1.8, max_drawdown=0.08,
                total_return=0.12, num_trades=45, avg_trade_pnl=250.0,
                rolling_window_days=30, mode=TradingModeEnum.PAPER,
                timestamp=now,
            ))

        # -- Capital allocations --
        for model, weight, capital in [(momentum, 0.35, 35000), (mean_rev, 0.25, 25000), (ml_model, 0.40, 40000)]:
            session.add(CapitalAllocation(
                model_id=model.id, weight=weight, allocated_capital=capital,
                reason="Performance-based allocation", timestamp=now,
            ))

        # -- Portfolio snapshot --
        session.add(PortfolioSnapshot(
            total_equity=102500.0, cash=45000.0, positions_value=57500.0,
            unrealized_pnl=1200.0, realized_pnl=1300.0, num_open_positions=3,
            exposure_pct=0.56, drawdown_pct=0.02, mode=TradingModeEnum.PAPER,
            positions_detail={"AAPL": 100, "NVDA": 30},
            timestamp=now,
        ))

        # -- Market regime --
        session.add(MarketRegimeRecord(
            regime=MarketRegime.LOW_VOL_BULL, confidence=0.82,
            volatility_20d=0.14, trend_strength=0.65,
            metadata_json={"vix": 14.2}, timestamp=now,
        ))

        # -- Risk event --
        session.add(RiskEvent(
            event_type=RiskEventType.TRADE_FREQUENCY_LIMIT, severity="info",
            description="Approaching hourly trade limit (18/20)",
            model_id=ml_model.id, action_taken="Throttled order submission",
            timestamp=now - timedelta(hours=2),
        ))

        session.commit()
        print("Seeded example data successfully:")
        print(f"  - 3 trading models")
        print(f"  - 3 trades")
        print(f"  - 3 performance records")
        print(f"  - 3 capital allocations")
        print(f"  - 1 portfolio snapshot")
        print(f"  - 1 market regime record")
        print(f"  - 1 risk event")


if __name__ == "__main__":
    seed()
