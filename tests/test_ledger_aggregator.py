"""Unit tests for ledger aggregation. All mocked."""

def test_total_equals_broker_plus_options_pnl():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._combine(broker_equity=1_000_000.0, options_sim_pnl=1_250.0)
    assert result["total_simulated_equity"] == 1_001_250.0
    assert result["broker_equity"] == 1_000_000.0
    assert result["options_sim_pnl"] == 1_250.0

def test_no_fallback_means_zero_options_pnl():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._combine(broker_equity=500_000.0, options_sim_pnl=0.0)
    assert result["total_simulated_equity"] == 500_000.0
    assert result["options_sim_pnl"] == 0.0

def test_returns_pct_uses_total_equity():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._compute_metrics(
        total_equity=1_010_000.0,
        initial_equity=1_000_000.0,
        equity_series=[1_000_000.0, 1_005_000.0, 1_010_000.0],
    )
    assert abs(result["returns_pct"] - 1.0) < 0.001

def test_drawdown_uses_total_equity():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    result = agg._compute_metrics(
        total_equity=1_000_000.0,
        initial_equity=1_000_000.0,
        equity_series=[1_000_000.0, 1_010_000.0, 1_000_000.0],
    )
    assert result["drawdown_pct"] > 0.0

def test_no_double_count_when_options_sim_disabled():
    from services.ledger_aggregator import LedgerAggregator
    agg = LedgerAggregator()
    broker_eq = 1_234_567.89
    result = agg._combine(broker_equity=broker_eq, options_sim_pnl=0.0)
    assert result["total_simulated_equity"] == broker_eq
