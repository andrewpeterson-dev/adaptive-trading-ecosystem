"""LangGraph state graph for multi-agent trade analysis.

Topology:
    START --> fan_out_analysts (no-op dispatcher)
          --> [technical_analyst, fundamental_analyst, sentiment_analyst]  (parallel)
          --> fan_in_analysts (no-op join)
          --> fan_out_researchers (no-op dispatcher)
          --> [bullish_researcher, bearish_researcher]                     (parallel)
          --> fan_in_researchers (no-op join)
          --> risk_assessor
          --> decision_synthesizer --> END

Fan-out / fan-in is achieved via conditional edges that return lists
of node names (LangGraph executes listed nodes in parallel) and
merge nodes that simply pass state through.
"""

from __future__ import annotations

import structlog
from langgraph.graph import END, START, StateGraph

from services.ai_core.multi_agent.state import TradeAnalysisState
from services.ai_core.multi_agent.nodes import (
    technical_analyst,
    fundamental_analyst,
    sentiment_analyst,
    bullish_researcher,
    bearish_researcher,
    risk_assessor,
    decision_synthesizer,
)

logger = structlog.get_logger(__name__)


def _make_skippable(node_fn, node_name: str):
    """Wrap a node to return empty output if it's in skip_nodes."""
    report_key = node_name.replace("_analyst", "") + "_report"

    async def wrapper(state):
        if node_name in state.get("skip_nodes", []):
            return {report_key: "", "node_trace": [f"{node_name}: SKIPPED"]}
        return await node_fn(state)

    wrapper.__name__ = node_fn.__name__
    return wrapper


def build_trade_analysis_graph():
    """Construct and compile the multi-agent trade analysis graph.

    Uses conditional edges that return multiple node names to achieve
    parallel fan-out, and join nodes for fan-in synchronization.
    """

    graph = StateGraph(TradeAnalysisState)

    # ── Register all analysis nodes ──────────────────────────────────
    graph.add_node("technical_analyst", _make_skippable(technical_analyst, "technical_analyst"))
    graph.add_node("fundamental_analyst", _make_skippable(fundamental_analyst, "fundamental_analyst"))
    graph.add_node("sentiment_analyst", _make_skippable(sentiment_analyst, "sentiment_analyst"))
    graph.add_node("bullish_researcher", bullish_researcher)
    graph.add_node("bearish_researcher", bearish_researcher)
    graph.add_node("risk_assessor", risk_assessor)
    graph.add_node("decision_synthesizer", decision_synthesizer)

    # ── Parallel fan-out from START to 3 analysts ────────────────────
    # Using conditional_edges with a function that returns a list of
    # node names tells LangGraph to run them in parallel.
    graph.add_conditional_edges(
        START,
        lambda state: ["technical_analyst", "fundamental_analyst", "sentiment_analyst"],
        ["technical_analyst", "fundamental_analyst", "sentiment_analyst"],
    )

    # ── Parallel fan-out from analysts to 2 researchers ──────────────
    # Each analyst feeds into both researchers (fan-in at researchers).
    # LangGraph waits for all incoming edges before executing a node.
    graph.add_conditional_edges(
        "technical_analyst",
        lambda state: ["bullish_researcher", "bearish_researcher"],
        ["bullish_researcher", "bearish_researcher"],
    )
    graph.add_conditional_edges(
        "fundamental_analyst",
        lambda state: ["bullish_researcher", "bearish_researcher"],
        ["bullish_researcher", "bearish_researcher"],
    )
    graph.add_conditional_edges(
        "sentiment_analyst",
        lambda state: ["bullish_researcher", "bearish_researcher"],
        ["bullish_researcher", "bearish_researcher"],
    )

    # ── Both researchers feed into risk_assessor ─────────────────────
    graph.add_edge("bullish_researcher", "risk_assessor")
    graph.add_edge("bearish_researcher", "risk_assessor")

    # ── risk_assessor -> decision_synthesizer -> END ─────────────────
    graph.add_edge("risk_assessor", "decision_synthesizer")
    graph.add_edge("decision_synthesizer", END)

    return graph.compile()


# Module-level singleton so it's compiled once
_compiled_graph = None


def get_trade_analysis_graph():
    """Return the compiled trade analysis graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_trade_analysis_graph()
        logger.info("trade_analysis_graph_compiled")
    return _compiled_graph
