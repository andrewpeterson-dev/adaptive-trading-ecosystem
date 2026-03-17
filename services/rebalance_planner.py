"""
Rebalance planner — compares current holdings to target weights
and produces a list of proposed trades to rebalance.

Takes into account:
- Minimum trade size thresholds
- Estimated transaction costs
- Tax-loss harvesting flag
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger(__name__)

# Minimum trade value to avoid dust trades
MIN_TRADE_VALUE = 50.0
# Estimated commission per trade (Webull is commission-free for stocks, but we model it)
DEFAULT_COMMISSION_PER_TRADE = 0.0
# Estimated slippage as a fraction of trade value
DEFAULT_SLIPPAGE_PCT = 0.001


@dataclass
class CurrentHolding:
    """A position currently held in the portfolio."""
    ticker: str
    quantity: float
    current_price: float
    market_value: float
    cost_basis: Optional[float] = None  # For tax-loss harvesting


@dataclass
class ProposedOrder:
    """A single order in the rebalance plan."""
    ticker: str
    action: str  # "buy" or "sell"
    shares: float
    estimated_cost: float
    reason: str
    current_weight: float
    target_weight: float
    weight_delta: float
    is_tax_loss_harvest: bool = False


@dataclass
class RebalancePlan:
    """The full rebalance plan."""
    orders: List[ProposedOrder]
    total_portfolio_value: float
    cash_available: float
    estimated_total_cost: float
    num_buys: int
    num_sells: int
    tax_loss_harvest_count: int
    metadata: Dict[str, Any] = field(default_factory=dict)


def compute_rebalance_plan(
    holdings: List[CurrentHolding],
    target_weights: Dict[str, float],
    total_portfolio_value: float,
    cash_available: float,
    min_trade_value: float = MIN_TRADE_VALUE,
    commission_per_trade: float = DEFAULT_COMMISSION_PER_TRADE,
    slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    enable_tax_loss_harvesting: bool = False,
) -> RebalancePlan:
    """Compute the trades needed to move from current holdings to target weights.

    Args:
        holdings: Current positions with prices.
        target_weights: Dict of {ticker: weight} from the optimizer (sum to ~1.0).
        total_portfolio_value: Total account value (cash + positions).
        cash_available: Cash available for purchases.
        min_trade_value: Minimum notional trade size to avoid dust.
        commission_per_trade: Estimated commission per order.
        slippage_pct: Estimated slippage as fraction.
        enable_tax_loss_harvesting: If True, flag sells where cost_basis > market_value.
    """
    # Validate target weights sum to ~1.0
    weight_sum = sum(target_weights.values())
    if not (0.98 <= weight_sum <= 1.02):
        logger.warning("rebalance_target_weights_sum_off", total=weight_sum)

    orders: List[ProposedOrder] = []

    # Build a map of current positions
    current_positions: Dict[str, CurrentHolding] = {}
    for h in holdings:
        current_positions[h.ticker] = h

    # Get the universe of all tickers (current + target)
    all_tickers = set(list(target_weights.keys()) + list(current_positions.keys()))

    # Current prices lookup (from holdings; for new tickers we'd need live quotes)
    prices: Dict[str, float] = {}
    for h in holdings:
        prices[h.ticker] = h.current_price

    for ticker in all_tickers:
        current_holding = current_positions.get(ticker)
        current_value = current_holding.market_value if current_holding else 0.0
        current_weight = current_value / total_portfolio_value if total_portfolio_value > 0 else 0.0

        target_weight = target_weights.get(ticker, 0.0)
        target_value = target_weight * total_portfolio_value
        value_delta = target_value - current_value
        weight_delta = target_weight - current_weight

        # Skip if the trade is below the minimum threshold
        if abs(value_delta) < min_trade_value:
            continue

        price = prices.get(ticker, 0.0)
        if price <= 0:
            logger.warning("rebalance_missing_price", ticker=ticker)
            continue

        shares = abs(value_delta) / price
        # Round to whole shares for simplicity
        shares = round(shares, 2)
        if shares <= 0:
            continue

        estimated_cost = commission_per_trade + (abs(value_delta) * slippage_pct)

        if value_delta > 0:
            action = "buy"
            reason = f"Increase weight from {current_weight:.1%} to {target_weight:.1%}"
        else:
            action = "sell"
            reason = f"Reduce weight from {current_weight:.1%} to {target_weight:.1%}"

        is_tlh = False
        if (
            enable_tax_loss_harvesting
            and action == "sell"
            and current_holding
            and current_holding.cost_basis is not None
            and current_holding.market_value < current_holding.cost_basis
        ):
            is_tlh = True
            reason += " (tax-loss harvest candidate)"

        orders.append(ProposedOrder(
            ticker=ticker,
            action=action,
            shares=shares,
            estimated_cost=round(estimated_cost, 2),
            reason=reason,
            current_weight=round(current_weight, 4),
            target_weight=round(target_weight, 4),
            weight_delta=round(weight_delta, 4),
            is_tax_loss_harvest=is_tlh,
        ))

    # Sort: sells first (to free up cash), then buys
    orders.sort(key=lambda o: (0 if o.action == "sell" else 1, -abs(o.weight_delta)))

    return RebalancePlan(
        orders=orders,
        total_portfolio_value=round(total_portfolio_value, 2),
        cash_available=round(cash_available, 2),
        estimated_total_cost=round(sum(o.estimated_cost for o in orders), 2),
        num_buys=sum(1 for o in orders if o.action == "buy"),
        num_sells=sum(1 for o in orders if o.action == "sell"),
        tax_loss_harvest_count=sum(1 for o in orders if o.is_tax_loss_harvest),
    )


async def generate_rebalance_plan(
    holdings: List[CurrentHolding],
    target_weights: Dict[str, float],
    total_portfolio_value: float,
    cash_available: float,
    min_trade_value: float = MIN_TRADE_VALUE,
    enable_tax_loss_harvesting: bool = False,
) -> RebalancePlan:
    """Async wrapper for compute_rebalance_plan."""
    return await asyncio.to_thread(
        compute_rebalance_plan,
        holdings,
        target_weights,
        total_portfolio_value,
        cash_available,
        min_trade_value,
        enable_tax_loss_harvesting=enable_tax_loss_harvesting,
    )
