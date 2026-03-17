"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  RefreshCw,
  Unplug,
  Settings,
  LayoutGrid,
  PieChart,
  ShieldCheck,
  Lock,
  Unlock,
  Brain,
  BarChart3,
  Activity,
  Crosshair,
  TrendingUp,
  Receipt,
  Zap,
  Target,
} from "lucide-react";
import "react-grid-layout/css/styles.css";
import "react-resizable/css/styles.css";
import type { Account, Position, Order, RiskSummary } from "@/types/trading";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useTradingMode } from "@/hooks/useTradingMode";
import { useDashboardStore } from "@/stores/dashboard-store";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import {
  DashboardPanel,
  MetricsRow,
  MarketIntelligenceBar,
  AIReasoningPanel,
  AIScannerPanel,
  OpenPositionsPanel,
  TradeLogPanel,
  RiskMetricsPanel,
  StrategyPanel,
  EquityCurvePanel,
  PortfolioRiskDashPanel,
} from "@/components/dashboard";
import { ExecutionChart } from "@/components/dashboard/ExecutionChart";
import { PortfolioEquityChart } from "@/components/dashboard/PortfolioEquityChart";
import { DashboardGrid } from "@/components/dashboard/GridLayout";
import type { Layouts, LayoutItem } from "@/components/dashboard/GridLayout";
import { SentimentPanel } from "@/components/analytics/SentimentPanel";
import { MarketMoodWidget } from "@/components/dashboard/MarketMoodWidget";
import { DashboardSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";

// ---------------------------------------------------------------------------
// Default grid layout
// ---------------------------------------------------------------------------

const DEFAULT_LAYOUTS: Layouts = {
  lg: [
    { i: "strategy",        x: 0, y: 0,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-reasoning",    x: 0, y: 8,  w: 3, h: 8,  minW: 2, minH: 5 },
    { i: "ai-scanner",      x: 0, y: 16, w: 3, h: 7,  minW: 2, minH: 4 },
    { i: "execution-chart", x: 3, y: 0,  w: 6, h: 12, minW: 4, minH: 8 },
    { i: "risk-metrics",    x: 9, y: 0,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "sentiment",       x: 9, y: 6,  w: 3, h: 6,  minW: 2, minH: 4 },
    { i: "equity-curve",    x: 3, y: 12, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "open-positions",  x: 9, y: 12, w: 3, h: 7,  minW: 3, minH: 5 },
    { i: "portfolio-risk",  x: 0, y: 23, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "trade-log",       x: 6, y: 23, w: 6, h: 7,  minW: 3, minH: 5 },
  ],
  md: [
    { i: "strategy",        x: 0, y: 0,  w: 6, h: 7,  minW: 3, minH: 4 },
    { i: "ai-reasoning",    x: 6, y: 0,  w: 6, h: 7,  minW: 3, minH: 4 },
    { i: "ai-scanner",      x: 0, y: 7,  w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "execution-chart", x: 0, y: 13, w: 12, h: 11, minW: 6, minH: 8 },
    { i: "risk-metrics",    x: 6, y: 7,  w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "sentiment",       x: 0, y: 24, w: 6, h: 6,  minW: 3, minH: 4 },
    { i: "equity-curve",    x: 0, y: 30, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "open-positions",  x: 6, y: 24, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "portfolio-risk",  x: 0, y: 37, w: 6, h: 7,  minW: 3, minH: 5 },
    { i: "trade-log",       x: 6, y: 31, w: 6, h: 7,  minW: 3, minH: 5 },
  ],
};

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  // -- Data state --
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [equityCurve, setEquityCurve] = useState<{ date: string; equity: number; drawdown: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const { mode } = useTradingMode();

  // -- Layout state --
  const { isLayoutLocked, toggleLayoutLock, layouts, updateLayouts } =
    useDashboardStore();

  // Use stored layouts if they have the right keys, otherwise use defaults
  const activeLayouts = useMemo(() => {
    const stored = layouts?.lg;
    if (stored && stored.length >= 10) return layouts;
    return DEFAULT_LAYOUTS;
  }, [layouts]);

  // -- Data fetching --
  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const q = `?mode=${mode}`;
      const [accRes, posRes, ordRes, riskRes, eqRes] = await Promise.allSettled([
        apiFetch<Account>(`/api/trading/account${q}`),
        apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
        apiFetch<{ orders: Order[] }>(`/api/trading/orders${q}`),
        apiFetch<RiskSummary>(`/api/trading/risk-summary${q}`),
        apiFetch<any>(`/api/dashboard/equity-curve${q}`),
      ]);

      if (accRes.status === "fulfilled") {
        setAccount(accRes.value);
        setError(false);
      } else {
        setError(true);
      }

      if (posRes.status === "fulfilled") {
        setPositions(posRes.value.positions || []);
      }

      if (ordRes.status === "fulfilled") {
        const list = ordRes.value.orders || [];
        setOrders(list.slice(0, 20));
      }

      if (riskRes.status === "fulfilled") {
        setRisk(riskRes.value);
      }

      if (eqRes.status === "fulfilled") {
        const eqData = eqRes.value;
        setEquityCurve(eqData.equity_curve || eqData || []);
      }

      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // -- Layout change handler --
  const handleLayoutChange = useCallback(
    (_layout: LayoutItem[], allLayouts: Layouts) => {
      if (!isLayoutLocked) {
        updateLayouts(allLayouts);
      }
    },
    [isLayoutLocked, updateLayouts]
  );

  // -- Derived metrics --
  const totalPnl = useMemo(() => {
    return positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  }, [positions]);

  const unrealizedPnl = totalPnl;
  const realizedPnl = null; // Not available — needs historical trade P&L data
  const hasRealizedPnl = false;

  const winRate = useMemo(() => {
    const filledOrders = orders.filter((o) => o.status === "filled");
    if (filledOrders.length === 0) return null; // No data yet
    // Simplified — would need trade P&L data for real win rate
    return null;
  }, [orders]);
  const hasWinRate = winRate !== null;

  // -- Early return states --
  if (loading) {
    return (
      <div className="app-page">
        <SubNav
          items={[
            { href: "/dashboard", label: "Overview", icon: LayoutGrid },
            { href: "/portfolio", label: "Portfolio", icon: PieChart },
            { href: "/risk", label: "Risk", icon: ShieldCheck },
          ]}
        />
        <DashboardSkeleton />
      </div>
    );
  }

  if (account?.not_configured) {
    return (
      <div className="app-page">
        <SubNav
          items={[
            { href: "/dashboard", label: "Overview", icon: LayoutGrid },
            { href: "/portfolio", label: "Portfolio", icon: PieChart },
            { href: "/risk", label: "Risk", icon: ShieldCheck },
          ]}
        />
        <EmptyState
          icon={<Unplug className="h-6 w-6 text-amber-400" />}
          title="No live trading configured"
          description={
            account.message ||
            "Connect a live API key in Settings to trade with real money."
          }
          action={
            <Link
              href="/settings"
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
            >
              <Settings className="h-4 w-4" />
              Go to Settings
            </Link>
          }
        />
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="app-page">
        <SubNav
          items={[
            { href: "/dashboard", label: "Overview", icon: LayoutGrid },
            { href: "/portfolio", label: "Portfolio", icon: PieChart },
            { href: "/risk", label: "Risk", icon: ShieldCheck },
          ]}
        />
        <EmptyState
          icon={<Unplug className="h-6 w-6 text-muted-foreground/60" />}
          title="Broker not responding"
          description="Could not load account data. Your API key may need to be re-entered."
          action={
            <div className="flex items-center justify-center gap-3">
              <button
                onClick={fetchAll}
                className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary px-4 py-2 text-sm font-medium hover:bg-secondary/80 transition-colors"
              >
                <RefreshCw className="h-4 w-4" />
                Retry
              </button>
              <Link
                href="/settings"
                className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <Settings className="h-4 w-4" />
                Go to Settings
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  return (
    <div
      className={cn("app-page", isLayoutLocked ? "layout-locked" : "layout-unlocked")}
    >
      {/* SubNav */}
      <SubNav
        items={[
          { href: "/dashboard", label: "Overview", icon: LayoutGrid },
          { href: "/portfolio", label: "Portfolio", icon: PieChart },
          { href: "/risk", label: "Risk", icon: ShieldCheck },
        ]}
      />

      {/* Page Header */}
      <PageHeader
        eyebrow="Overview"
        title="Trading Dashboard"
        description="Real-time portfolio analytics, AI signals, and execution monitoring."
        badge={
          <StatusChip
            variant={mode === "live" ? "live" : "paper"}
            label={mode === "live" ? "LIVE MODE" : "PAPER MODE"}
            pulse
          />
        }
        meta={
          lastRefresh ? (
            <span className="app-pill font-mono tracking-normal">
              Updated {lastRefresh.toLocaleTimeString()}
            </span>
          ) : undefined
        }
        actions={
          <div className="flex items-center gap-2">
            <button
              onClick={toggleLayoutLock}
              className={cn(
                "app-button-secondary !px-3 !py-2",
                !isLayoutLocked && "!border-primary/40 !bg-primary/5"
              )}
              title={isLayoutLocked ? "Unlock layout" : "Lock layout"}
            >
              {isLayoutLocked ? (
                <Lock className="h-4 w-4" />
              ) : (
                <Unlock className="h-4 w-4 text-primary" />
              )}
              <span className="text-xs">
                {isLayoutLocked ? "Layout Locked" : "Editing Layout"}
              </span>
            </button>
            <button onClick={fetchAll} className="app-button-secondary">
              <RefreshCw className="h-4 w-4" />
              Refresh
            </button>
          </div>
        }
      />

      {/* Row 1: Metrics (outside grid — always full width, never draggable) */}
      <MetricsRow
        totalPnl={totalPnl}
        unrealizedPnl={unrealizedPnl}
        realizedPnl={realizedPnl ?? 0}
        expectancy={0}
        winRate={winRate ?? 0}
        maxDrawdown={risk?.current_drawdown_pct ?? 0}
        exposure={risk?.current_exposure_pct ?? 0}
        tradesToday={risk?.trades_this_hour ?? 0}
        tradeHistory={[]}
        realizedPnlUnavailable={!hasRealizedPnl}
        winRateUnavailable={!hasWinRate}
      />

      {/* Market Intelligence Bar (outside grid — static, never draggable) */}
      <MarketIntelligenceBar
        trend={{ direction: "bullish", label: "Bullish" }}
        volatility={{ vix: 16.4, level: "low" }}
        sentiment="risk-on"
        bestSector="Technology"
        strategyStatus={{ active: positions.length > 0, name: "AI Momentum" }}
      />

      {/* Grid Layout */}
      <DashboardGrid
        layouts={activeLayouts}
        isDraggable={!isLayoutLocked}
        isResizable={!isLayoutLocked}
        onLayoutChange={handleLayoutChange}
      >
          {/* Left Column */}
          <div key="strategy">
            <DashboardPanel title="Strategies" icon={Zap}>
              <StrategyPanel strategies={[]} />
            </DashboardPanel>
          </div>

          <div key="ai-reasoning">
            <DashboardPanel title="AI Reasoning" icon={Brain}>
              <AIReasoningPanel decision={null} />
            </DashboardPanel>
          </div>

          <div key="ai-scanner">
            <DashboardPanel title="AI Scanner" icon={Crosshair}>
              <AIScannerPanel totalWatching={0} signals={[]} />
            </DashboardPanel>
          </div>

          {/* Center Column */}
          <div key="execution-chart">
            <DashboardPanel title="Portfolio Equity" icon={TrendingUp} noPadding>
              <PortfolioEquityChart height={340} />
            </DashboardPanel>
          </div>

          {/* Right Column */}
          <div key="risk-metrics">
            <DashboardPanel title="Risk Metrics" icon={ShieldCheck}>
              <RiskMetricsPanel
                winRate={winRate ?? 0}
                maxDrawdown={risk?.current_drawdown_pct ?? 0}
                totalTrades={orders.filter((o) => o.status === "filled").length}
              />
            </DashboardPanel>
          </div>

          <div key="sentiment">
            <DashboardPanel title="Market Sentiment" icon={Activity}>
              <MarketMoodWidget />
            </DashboardPanel>
          </div>

          {/* Row 3 */}
          <div key="equity-curve">
            <DashboardPanel title="Equity Curve" icon={TrendingUp}>
              <EquityCurvePanel data={equityCurve} />
            </DashboardPanel>
          </div>

          <div key="open-positions">
            <DashboardPanel
              title="Open Positions"
              icon={Target}
              noPadding
              onRefresh={fetchAll}
            >
              <OpenPositionsPanel positions={positions} />
            </DashboardPanel>
          </div>

          {/* Row 4 */}
          <div key="portfolio-risk">
            <DashboardPanel title="Portfolio Risk" icon={ShieldCheck}>
              <PortfolioRiskDashPanel
                totalExposure={risk?.current_exposure_pct ?? 0}
              />
            </DashboardPanel>
          </div>

          <div key="trade-log">
            <DashboardPanel
              title="Trade Log"
              icon={Receipt}
              noPadding
              onRefresh={fetchAll}
            >
              <TradeLogPanel orders={orders} />
            </DashboardPanel>
          </div>
      </DashboardGrid>
    </div>
  );
}
