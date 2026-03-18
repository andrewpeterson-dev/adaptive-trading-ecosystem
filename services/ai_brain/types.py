"""Data types for the AI Brain trading engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AITradeDecision:
    """Structured decision output from AITradingEngine."""

    action: str  # BUY, SELL, HOLD, EXIT
    symbol: str
    quantity: float
    confidence: float  # 0.0 - 1.0
    reasoning_summary: str  # 2-3 sentence summary (Tier B)
    reasoning_full: dict = field(default_factory=dict)  # Node-by-node breakdown (Tier C)
    data_contributions: dict = field(default_factory=dict)  # Source weights
    model_used: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_dict(self) -> dict:
        return {
            "action": self.action,
            "symbol": self.symbol,
            "quantity": self.quantity,
            "confidence": self.confidence,
            "reasoning_summary": self.reasoning_summary,
            "reasoning_full": self.reasoning_full,
            "data_contributions": self.data_contributions,
            "model_used": self.model_used,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class AIBrainConfig:
    """Parsed ai_brain_config from CerberusBot."""

    execution_mode: str = "manual"
    data_sources: list = field(default_factory=lambda: ["technical"])
    trading_thesis: str = ""
    primary_model: str = "gpt-5.4"
    ensemble_mode: bool = False
    ensemble_models: list = field(default_factory=list)
    comparison_models: list = field(default_factory=list)
    universe_mode: str = "fixed"
    universe_symbols: list = field(default_factory=list)
    universe_blacklist: list = field(default_factory=list)
    max_trades_per_day: int = 10
    max_position_pct: float = 10.0
    allowed_sides: list = field(default_factory=lambda: ["long", "short"])

    @classmethod
    def from_json(cls, data: Optional[dict]) -> "AIBrainConfig":
        if not data:
            return cls()
        model_config = data.get("model_config", {})
        universe = data.get("universe", {})
        constraints = data.get("constraints", {})
        return cls(
            execution_mode=data.get("execution_mode", "manual"),
            data_sources=data.get("data_sources", ["technical"]),
            trading_thesis=data.get("trading_thesis", ""),
            primary_model=model_config.get("primary_model", "gpt-5.4"),
            ensemble_mode=model_config.get("ensemble_mode", False),
            ensemble_models=model_config.get("ensemble_models", []),
            comparison_models=data.get("comparison_models", []),
            universe_mode=universe.get("mode", "fixed"),
            universe_symbols=universe.get("symbols", []),
            universe_blacklist=universe.get("blacklist", []),
            max_trades_per_day=constraints.get("max_trades_per_day", 10),
            max_position_pct=constraints.get("max_position_pct", 10.0),
            allowed_sides=constraints.get("allowed_sides", ["long", "short"]),
        )
