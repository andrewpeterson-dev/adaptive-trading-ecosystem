"""
Ledger aggregator.

Computes combined performance metrics from:
  ledgerBroker     — equity from active broker (Webull paper)
  ledgerOptionsSim — P&L from options sim trades (Tradier paper)

Never double-counts: options sim tracks P&L only, not cash.
"""
from __future__ import annotations
from typing import Optional
import math
import structlog
from sqlalchemy import select, func
from db.database import get_session
from db.models import OptionSimTrade

logger = structlog.get_logger(__name__)


class LedgerAggregator:

    def _combine(self, *, broker_equity: float, options_sim_pnl: float) -> dict:
        return {
            "broker_equity": broker_equity,
            "options_sim_pnl": options_sim_pnl,
            "total_simulated_equity": broker_equity + options_sim_pnl,
        }

    def _compute_metrics(self, *, total_equity: float, initial_equity: float, equity_series: list) -> dict:
        returns_pct = ((total_equity - initial_equity) / initial_equity * 100) if initial_equity else 0.0
        peak = equity_series[0] if equity_series else total_equity
        drawdown_pct = 0.0
        for v in equity_series:
            peak = max(peak, v)
            dd = (peak - v) / peak * 100 if peak else 0.0
            drawdown_pct = max(drawdown_pct, dd)
        sharpe = 0.0
        if len(equity_series) >= 2:
            daily_rets = [(equity_series[i] - equity_series[i-1]) / equity_series[i-1]
                          for i in range(1, len(equity_series))
                          if equity_series[i-1] != 0]
            if daily_rets:
                mean_r = sum(daily_rets) / len(daily_rets)
                variance = sum((r - mean_r)**2 for r in daily_rets) / len(daily_rets)
                std_r = math.sqrt(variance) if variance > 0 else 0.0
                sharpe = (mean_r / std_r * math.sqrt(252)) if std_r > 0 else 0.0
        return {
            "returns_pct": round(returns_pct, 4),
            "drawdown_pct": round(drawdown_pct, 4),
            "sharpe": round(sharpe, 4),
        }

    async def get_options_sim_pnl(self, user_id: int) -> tuple:
        async with get_session() as db:
            r = await db.execute(
                select(func.coalesce(func.sum(OptionSimTrade.realized_pnl), 0.0))
                .where(OptionSimTrade.user_id == user_id, OptionSimTrade.status == "closed")
            )
            realized_pnl = float(r.scalar() or 0.0)
            r2 = await db.execute(
                select(OptionSimTrade).where(
                    OptionSimTrade.user_id == user_id, OptionSimTrade.status == "open"
                )
            )
            open_trades = r2.scalars().all()
            open_positions = [
                {"id": t.id, "symbol": t.symbol, "option_symbol": t.option_symbol,
                 "option_type": t.option_type, "strike": t.strike,
                 "expiry": str(t.expiry), "qty": t.qty, "fill_price": t.fill_price}
                for t in open_trades
            ]
        return realized_pnl, open_positions

    async def build_combined(self, *, user_id: int, broker_equity: float, broker_label: str,
                              initial_equity: float, options_label: Optional[str] = None,
                              equity_series: Optional[list] = None,
                              options_fallback_enabled: bool = False) -> dict:
        options_sim_pnl = 0.0
        open_positions: list = []
        if options_fallback_enabled:
            options_sim_pnl, open_positions = await self.get_options_sim_pnl(user_id)
        combined = self._combine(broker_equity=broker_equity, options_sim_pnl=options_sim_pnl)
        series = equity_series or [initial_equity, combined["total_simulated_equity"]]
        metrics = self._compute_metrics(
            total_equity=combined["total_simulated_equity"],
            initial_equity=initial_equity,
            equity_series=series,
        )
        return {
            **combined,
            "broker_label": broker_label,
            "options_label": options_label or "Options Sim",
            "open_options_positions": open_positions,
            "metrics": metrics,
        }


ledger_aggregator = LedgerAggregator()
