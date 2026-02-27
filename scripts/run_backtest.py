"""
Standalone backtest runner.
Trains all models, runs walk-forward backtests, and prints comparative results.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.ingestion import DataIngestor
from engine.backtester import BacktestEngine
from models.registry import create_default_models


def main():
    print("=== Adaptive Trading Ecosystem — Backtest Runner ===\n")

    # Fetch data
    ingestor = DataIngestor()
    symbols = ["SPY"]
    print(f"Fetching data for {symbols}...")

    from datetime import datetime, timedelta
    from alpaca.data.timeframe import TimeFrame

    start = datetime.utcnow() - timedelta(days=500)
    df = ingestor.fetch_bars(symbols, start=start, timeframe=TimeFrame.Day)

    if df.empty:
        print("ERROR: No data fetched. Check API keys.")
        return

    print(f"Data shape: {df.shape}\n")

    # Create models
    models = create_default_models()
    print(f"Models: {[m.name for m in models]}\n")

    # Run backtests
    engine = BacktestEngine(slippage_bps=5.0, commission_per_share=0.005)

    print("Running walk-forward backtests...\n")
    results = {}
    for model in models:
        print(f"  Backtesting: {model.name}...")
        result = engine.run_walk_forward(model, df, train_window=200, test_window=20)
        results[model.name] = result

    # Print results
    print("\n" + "=" * 80)
    print(f"{'Model':<25} {'Sharpe':>8} {'Win%':>8} {'MaxDD':>8} {'Return':>10} {'Trades':>8}")
    print("-" * 80)
    for name, r in results.items():
        m = r.metrics
        print(
            f"{name:<25} {m.sharpe_ratio:>8.3f} {m.win_rate:>7.1%} "
            f"{m.max_drawdown:>8.2%} {m.total_return:>9.2%} {m.num_trades:>8}"
        )
    print("=" * 80)


if __name__ == "__main__":
    main()
