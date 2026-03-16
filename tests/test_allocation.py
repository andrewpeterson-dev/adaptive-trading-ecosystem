"""
Tests for the capital allocation engine.
"""

import os

os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from allocation.capital import CapitalAllocator
from models.momentum import MomentumModel
from models.mean_reversion import MeanReversionModel


class TestCapitalAllocator:
    def test_equal_weights_no_performance(self):
        allocator = CapitalAllocator(total_capital=100_000)
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        weights = allocator.compute_weights([m1, m2])
        assert len(weights) == 2
        assert abs(sum(weights.values()) - 1.0) < 1e-6

    def test_performance_weighted(self):
        allocator = CapitalAllocator(total_capital=100_000)
        allocator.min_weight = 0.0
        allocator.max_weight = 1.0
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        m1.metrics.sharpe_ratio = 2.0
        m1.metrics.sortino_ratio = 2.5
        m1.metrics.profit_factor = 2.0
        m1.metrics.num_trades = 50
        m2.metrics.sharpe_ratio = 0.5
        m2.metrics.sortino_ratio = 0.3
        m2.metrics.profit_factor = 1.1
        m2.metrics.num_trades = 50

        weights = allocator.compute_weights([m1, m2])
        assert weights["m1"] > weights["m2"]

    def test_min_weight_constraint(self):
        allocator = CapitalAllocator(total_capital=100_000)
        allocator.min_weight = 0.10
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        m1.metrics.sharpe_ratio = 10.0
        m1.metrics.num_trades = 100
        m2.metrics.sharpe_ratio = 0.01
        m2.metrics.num_trades = 100

        weights = allocator.compute_weights([m1, m2])
        assert weights["m2"] >= allocator.min_weight - 0.01  # Float tolerance

    def test_capital_map_sums_correctly(self):
        allocator = CapitalAllocator(total_capital=100_000)
        m1 = MomentumModel(name="m1")
        m2 = MeanReversionModel(name="m2")
        allocator.compute_weights([m1, m2])
        total = sum(allocator.capital_map.values())
        assert abs(total - 100_000) < 1.0
