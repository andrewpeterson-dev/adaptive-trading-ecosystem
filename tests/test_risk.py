"""
Tests for the risk management layer.
"""

import os

# Override settings before import
os.environ.setdefault("ALPACA_API_KEY", "test")
os.environ.setdefault("ALPACA_SECRET_KEY", "test")

from models.base import Signal
from risk.manager import RiskManager


class TestRiskManager:
    def _make_signal(self, symbol="SPY", direction="long"):
        return Signal(symbol=symbol, direction=direction, strength=0.8, model_name="test")

    def test_approve_valid_trade(self):
        rm = RiskManager()
        signal = self._make_signal()
        approved, size, reason = rm.validate_trade(
            signal=signal,
            proposed_size=10,
            current_equity=100_000,
            current_exposure=0,
            current_price=450,
        )
        assert approved
        assert size > 0
        assert reason == "approved"

    def test_reject_when_halted(self):
        rm = RiskManager()
        rm._halt_trading("test halt")
        signal = self._make_signal()
        approved, size, reason = rm.validate_trade(
            signal=signal,
            proposed_size=10,
            current_equity=100_000,
            current_exposure=0,
            current_price=450,
        )
        assert not approved
        assert "halted" in reason.lower()

    def test_cap_position_size(self):
        rm = RiskManager()
        rm.max_position_size_pct = 0.05  # 5%
        signal = self._make_signal()
        approved, size, reason = rm.validate_trade(
            signal=signal,
            proposed_size=100,  # Way too large
            current_equity=100_000,
            current_exposure=0,
            current_price=450,
        )
        assert approved
        max_value = 100_000 * 0.05
        assert size * 450 <= max_value + 1  # Allow tiny float error

    def test_reject_at_max_exposure(self):
        rm = RiskManager()
        rm.max_portfolio_exposure_pct = 0.80
        signal = self._make_signal()
        approved, size, reason = rm.validate_trade(
            signal=signal,
            proposed_size=10,
            current_equity=100_000,
            current_exposure=80_000,  # Already at limit
            current_price=450,
        )
        assert not approved

    def test_drawdown_shutdown(self):
        rm = RiskManager()
        rm.max_drawdown_pct = 0.15
        rm._peak_equity = 100_000
        signal = self._make_signal()
        approved, size, reason = rm.validate_trade(
            signal=signal,
            proposed_size=10,
            current_equity=84_000,  # 16% drawdown
            current_exposure=0,
            current_price=450,
        )
        assert not approved
        assert rm.is_halted

    def test_trade_frequency_limit(self):
        rm = RiskManager()
        rm.max_trades_per_hour = 3
        signal = self._make_signal()

        for i in range(3):
            approved, _, _ = rm.validate_trade(
                signal=signal, proposed_size=1, current_equity=100_000,
                current_exposure=0, current_price=450,
            )
            assert approved

        approved, _, reason = rm.validate_trade(
            signal=signal, proposed_size=1, current_equity=100_000,
            current_exposure=0, current_price=450,
        )
        assert not approved
        assert "frequency" in reason.lower()

    def test_stop_loss(self):
        rm = RiskManager()
        rm.stop_loss_pct = 0.03
        rm.register_position("AAPL", entry_price=200, size=10, direction="long")
        assert not rm.check_stop_loss("AAPL", 198)   # 1% loss — ok
        assert rm.check_stop_loss("AAPL", 193)        # 3.5% loss — triggered

    def test_resume_trading(self):
        rm = RiskManager()
        rm._halt_trading("test")
        assert rm.is_halted
        rm.resume_trading()
        assert not rm.is_halted
