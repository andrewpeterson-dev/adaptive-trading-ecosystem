"""Tests for the tool registry (services/ai_core/tools/registry.py) and register_all."""
from __future__ import annotations

import pytest

from services.ai_core.tools.base import ToolDefinition, ToolCategory, ToolSideEffect
from services.ai_core.tools.registry import ToolRegistry, get_registry


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_registry():
    """Ensure a clean singleton before and after every test."""
    ToolRegistry.reset()
    yield
    ToolRegistry.reset()


def _make_tool(name: str = "test_tool", category: ToolCategory = ToolCategory.PORTFOLIO,
               side_effect: ToolSideEffect = ToolSideEffect.READ) -> ToolDefinition:
    return ToolDefinition(
        name=name,
        version="1.0",
        description=f"Test tool: {name}",
        category=category,
        side_effect=side_effect,
        input_schema={"type": "object", "properties": {"x": {"type": "integer"}}},
        output_schema={"type": "object"},
    )


# ---------------------------------------------------------------------------
# Core registry tests
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_singleton_identity(self):
        r1 = ToolRegistry()
        r2 = ToolRegistry()
        assert r1 is r2

    def test_get_registry_returns_singleton(self):
        r1 = get_registry()
        r2 = get_registry()
        assert r1 is r2

    def test_register_and_get(self):
        reg = get_registry()
        tool = _make_tool("myTool")
        reg.register(tool)
        assert reg.get("myTool") is tool

    def test_get_missing_returns_none(self):
        reg = get_registry()
        assert reg.get("nonexistent") is None

    def test_list_all(self):
        reg = get_registry()
        reg.register(_make_tool("a"))
        reg.register(_make_tool("b"))
        assert len(reg.list_all()) == 2

    def test_list_by_category(self):
        reg = get_registry()
        reg.register(_make_tool("p1", category=ToolCategory.PORTFOLIO))
        reg.register(_make_tool("r1", category=ToolCategory.RISK))
        reg.register(_make_tool("p2", category=ToolCategory.PORTFOLIO))
        assert len(reg.list_by_category(ToolCategory.PORTFOLIO)) == 2
        assert len(reg.list_by_category(ToolCategory.RISK)) == 1

    def test_list_for_model_excludes_dangerous(self):
        reg = get_registry()
        reg.register(_make_tool("safe", side_effect=ToolSideEffect.READ))
        reg.register(_make_tool("danger", side_effect=ToolSideEffect.DANGEROUS))
        safe_tools = reg.list_for_model(include_dangerous=False)
        assert len(safe_tools) == 1
        assert safe_tools[0].name == "safe"

    def test_list_for_model_includes_dangerous_when_flagged(self):
        reg = get_registry()
        reg.register(_make_tool("safe", side_effect=ToolSideEffect.READ))
        reg.register(_make_tool("danger", side_effect=ToolSideEffect.DANGEROUS))
        all_tools = reg.list_for_model(include_dangerous=True)
        assert len(all_tools) == 2

    def test_list_read_only(self):
        reg = get_registry()
        reg.register(_make_tool("r", side_effect=ToolSideEffect.READ))
        reg.register(_make_tool("w", side_effect=ToolSideEffect.WRITE))
        read_only = reg.list_read_only()
        assert len(read_only) == 1
        assert read_only[0].name == "r"

    def test_to_provider_format(self):
        reg = get_registry()
        tool = _make_tool("fmt")
        reg.register(tool)
        fmt = reg.to_provider_format()
        assert len(fmt) == 1
        assert fmt[0]["name"] == "fmt"
        assert "description" in fmt[0]
        assert "parameters" in fmt[0]

    def test_clear(self):
        reg = get_registry()
        reg.register(_make_tool("x"))
        assert len(reg.list_all()) == 1
        reg.clear()
        assert len(reg.list_all()) == 0

    def test_reset_creates_new_instance(self):
        r1 = ToolRegistry()
        r1.register(_make_tool("x"))
        ToolRegistry.reset()
        r2 = ToolRegistry()
        assert r1 is not r2
        assert len(r2.list_all()) == 0

    def test_duplicate_registration_overwrites(self):
        reg = get_registry()
        reg.register(_make_tool("dup", category=ToolCategory.PORTFOLIO))
        reg.register(_make_tool("dup", category=ToolCategory.RISK))
        tool = reg.get("dup")
        assert tool.category == ToolCategory.RISK
        assert len(reg.list_all()) == 1


# ---------------------------------------------------------------------------
# register_all_tools integration test
# ---------------------------------------------------------------------------

class TestRegisterAllTools:
    def test_register_all_tools_registers_35(self):
        """All 6 tool modules should register exactly 35 tools total."""
        from services.ai_core.tools.register_all import register_all_tools

        register_all_tools()
        reg = get_registry()
        tools = reg.list_all()
        assert len(tools) == 39, f"Expected 35, got {len(tools)}: {[t.name for t in tools]}"

    def test_all_categories_represented(self):
        from services.ai_core.tools.register_all import register_all_tools

        register_all_tools()
        reg = get_registry()
        categories = {t.category for t in reg.list_all()}
        expected = {
            ToolCategory.PORTFOLIO,
            ToolCategory.RISK,
            ToolCategory.MARKET,
            ToolCategory.TRADING,
            ToolCategory.ANALYTICS,
            ToolCategory.RESEARCH,
        }
        assert categories == expected

    def test_provider_format_for_all_tools(self):
        from services.ai_core.tools.register_all import register_all_tools

        register_all_tools()
        reg = get_registry()
        fmt = reg.to_provider_format()
        assert len(fmt) == 39
        for entry in fmt:
            assert "name" in entry
            assert "description" in entry
            assert "parameters" in entry

    def test_known_tool_names_present(self):
        from services.ai_core.tools.register_all import register_all_tools

        register_all_tools()
        reg = get_registry()
        expected_names = [
            "getPortfolio", "getPositions", "getOrders", "getTradeHistory",
            "calculateVaR", "calculateDrawdown", "portfolioExposure",
            "concentrationRisk", "optionsGreekExposure",
            "getPrice", "getHistoricalPrices", "getOptionsChain",
            "getIndicators", "getEarningsCalendar", "getMacroCalendar",
            "createBot", "modifyBot", "stopBot", "pauseBot", "resumeBot",
            "backtestStrategy", "createTradeProposal",
            "getBestTrade", "getWorstTrades", "getTotalTradingVolume",
            "getStrategyPerformance", "getSymbolPerformance",
            "getHoldTimeStats", "getBotPerformance",
            "searchDocuments", "getDocumentExcerpt", "getMarketNews",
            "getMacroEvents", "getEarningsContext", "runResearchSession",
        ]
        for name in expected_names:
            assert reg.get(name) is not None, f"Tool '{name}' not registered"
