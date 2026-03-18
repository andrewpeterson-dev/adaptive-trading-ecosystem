"""State definition for the multi-agent trade analysis pipeline."""

from __future__ import annotations

import operator
from dataclasses import dataclass, field
from typing import Annotated, Optional

from typing_extensions import TypedDict


class TradeAnalysisState(TypedDict, total=False):
    """Shared state passed through the LangGraph trade analysis pipeline.

    Analysts populate their reports in parallel, then researchers
    consume them to argue bull/bear cases.  The risk assessor and
    decision synthesizer run last.

    ``node_trace`` and ``errors`` use ``Annotated[list, operator.add]``
    so that parallel branches concatenate rather than overwrite.
    """

    # ── Input ────────────────────────────────────────────────────────
    symbol: str
    current_price: float
    proposed_action: str  # "buy" or "sell"
    proposed_size: float
    user_id: int

    # ── Analyst outputs ──────────────────────────────────────────────
    technical_report: str
    fundamental_report: str
    sentiment_report: str

    # ── Researcher outputs ───────────────────────────────────────────
    bull_case: str
    bear_case: str

    # ── Risk output ──────────────────────────────────────────────────
    risk_assessment: str

    # ── Final decision ───────────────────────────────────────────────
    recommendation: str  # strong_buy | buy | hold | sell | strong_sell
    confidence: float    # 0.0 to 1.0
    reasoning: str

    # ── AI Brain fields ──────────────────────────────────────────────
    trading_thesis: str
    model_override: str
    skip_nodes: list[str]
    macro_data: dict
    portfolio_data: dict

    # ── Metadata (reducible via operator.add for parallel merges) ────
    node_trace: Annotated[list, operator.add]
    errors: Annotated[list, operator.add]


@dataclass
class TradeAnalysisResult:
    """Structured result returned by the runner to callers."""

    analysis_id: str = ""
    symbol: str = ""
    action: str = ""
    proposed_size: float = 0.0
    current_price: float = 0.0

    technical_report: str = ""
    fundamental_report: str = ""
    sentiment_report: str = ""
    bull_case: str = ""
    bear_case: str = ""
    risk_assessment: str = ""

    recommendation: str = "hold"
    confidence: float = 0.0
    reasoning: str = ""

    trading_thesis: str = ""
    model_override: str = ""
    skip_nodes: list = field(default_factory=list)
    macro_data: dict = field(default_factory=dict)
    portfolio_data: dict = field(default_factory=dict)

    node_trace: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "analysis_id": self.analysis_id,
            "symbol": self.symbol,
            "action": self.action,
            "proposed_size": self.proposed_size,
            "current_price": self.current_price,
            "technical_report": self.technical_report,
            "fundamental_report": self.fundamental_report,
            "sentiment_report": self.sentiment_report,
            "bull_case": self.bull_case,
            "bear_case": self.bear_case,
            "risk_assessment": self.risk_assessment,
            "recommendation": self.recommendation,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "trading_thesis": self.trading_thesis,
            "model_override": self.model_override,
            "skip_nodes": self.skip_nodes,
            "macro_data": self.macro_data,
            "portfolio_data": self.portfolio_data,
            "node_trace": self.node_trace,
            "errors": self.errors,
        }
