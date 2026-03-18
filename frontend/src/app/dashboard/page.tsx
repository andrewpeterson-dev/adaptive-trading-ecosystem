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
  Activity,
  Crosshair,
  TrendingUp,
  Receipt,
  Zap,
  Target,
  ChevronDown,
  Radio,
} from "lucide-react";
import type { Account, Position, Order, RiskSummary } from "@/types/trading";
import { apiFetch } from "@/lib/api/client";
import { cn } from "@/lib/utils";
import { useTradingMode } from "@/hooks/useTradingMode";
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
import { PortfolioEquityChart } from "@/components/dashboard/PortfolioEquityChart";
import { AmbientBackground } from "@/components/dashboard/AmbientBackground";
import { MarketMoodWidget } from "@/components/dashboard/MarketMoodWidget";
import { DashboardSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { StatusChip } from "@/components/ui/status-chip";

// ---------------------------------------------------------------------------
// Collapsible Section — scan-first building block
// ---------------------------------------------------------------------------

function Section({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  badge,
  className = "",
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  badge?: React.ReactNode;
  className?: string;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section className={className}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 py-2 group"
      >
        <Icon className="h-3.5 w-3.5 text-muted-foreground/60" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground/70">
          {title}
        </span>
        {badge}
        <span className="flex-1" />
        <ChevronDown
          className={cn(
            "h-3 w-3 text-muted-foreground/40 transition-transform duration-200",
            !open && "-rotate-90"
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-300 ease-in-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="pt-1 pb-2">{children}</div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Tab Bar — for consolidating related panels
// ---------------------------------------------------------------------------

function TabBar({
  tabs,
  active,
  onChange,
}: {
  tabs: { key: string; label: string; icon?: React.ElementType }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex items-center gap-0.5 rounded-lg border border-border/40 bg-muted/10 p-0.5 w-fit mb-3">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        return (
          <button
            key={tab.key}
            type="button"
            onClick={() => onChange(tab.key)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[10px] font-semibold transition-all duration-150",
              active === tab.key
                ? "bg-foreground text-background shadow-sm"
                : "text-muted-foreground/60 hover:text-foreground hover:bg-white/[0.04]"
            )}
          >
            {Icon && <Icon className="h-3 w-3" />}
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cerberus Insight Chip — ambient AI presence
// ---------------------------------------------------------------------------

function CerberusInsightChip() {
  return (
    <div className="flex items-center gap-3 ml-auto w-fit rounded-full border border-border/40 cerberus-chip px-4 py-2 mt-3">
      <div className="signal-bars flex items-end gap-[2px]">
        <span className="block h-[6px] w-[2px] rounded-full bg-emerald-400/70" />
        <span className="block h-[9px] w-[2px] rounded-full bg-emerald-400/60" />
        <span className="block h-[12px] w-[2px] rounded-full bg-emerald-400/40" />
      </div>
      <span className="text-[11px] font-mono text-muted-foreground/60 tracking-wide">
        Cerberus AI
      </span>
      <span className="h-3 w-px bg-border/30" />
      <span className="text-[10px] font-mono text-muted-foreground/40">
        Market structure stable &bull; Regime: Normal
      </span>
    </div>
  );
}

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

  // -- Tab state for grouped sections --
  const [aiTab, setAiTab] = useState("reasoning");
  const [riskTab, setRiskTab] = useState("metrics");

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
        setOrders(ordRes.value.orders || []);
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

  // -- Derived metrics --
  const totalPnl = useMemo(() => {
    return positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  }, [positions]);

  const unrealizedPnl = totalPnl;
  const realizedPnl = null;
  const hasRealizedPnl = false;

  const filledOrderCount = useMemo(
    () => orders.filter((o) => o.status === "filled").length,
    [orders]
  );

  const winRate = useMemo(() => {
    if (filledOrderCount === 0) return null;
    return null;
  }, [filledOrderCount]);
  const hasWinRate = winRate !== null;

  // -- Early return states --
  if (loading) {
    return (
      <div className="app-page">
        <SubNav items={[
          { href: "/dashboard", label: "Overview", icon: LayoutGrid },
          { href: "/portfolio", label: "Portfolio", icon: PieChart },
          { href: "/risk", label: "Risk", icon: ShieldCheck },
        ]} />
        <DashboardSkeleton />
      </div>
    );
  }

  if (account?.not_configured) {
    return (
      <div className="app-page">
        <SubNav items={[
          { href: "/dashboard", label: "Overview", icon: LayoutGrid },
          { href: "/portfolio", label: "Portfolio", icon: PieChart },
          { href: "/risk", label: "Risk", icon: ShieldCheck },
        ]} />
        <EmptyState
          icon={<Unplug className="h-6 w-6 text-amber-400" />}
          title="No live trading configured"
          description={account.message || "Connect a live API key in Settings to trade with real money."}
          action={
            <Link href="/settings" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
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
        <SubNav items={[
          { href: "/dashboard", label: "Overview", icon: LayoutGrid },
          { href: "/portfolio", label: "Portfolio", icon: PieChart },
          { href: "/risk", label: "Risk", icon: ShieldCheck },
        ]} />
        <EmptyState
          icon={<Unplug className="h-6 w-6 text-muted-foreground/60" />}
          title="Broker not responding"
          description="Could not load account data. Your API key may need to be re-entered."
          action={
            <div className="flex items-center justify-center gap-3">
              <button onClick={fetchAll} className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary px-4 py-2 text-sm font-medium hover:bg-secondary/80 transition-colors">
                <RefreshCw className="h-4 w-4" />
                Retry
              </button>
              <Link href="/settings" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors">
                <Settings className="h-4 w-4" />
                Go to Settings
              </Link>
            </div>
          }
        />
      </div>
    );
  }

  // =========================================================================
  // MAIN DASHBOARD — scan-first control surface
  // =========================================================================

  return (
    <div className="app-page relative">
      <AmbientBackground />

      {/* ── ZONE 1: SYSTEM STATE ──────────────────────────────────── */}
      <SubNav items={[
        { href: "/dashboard", label: "Overview", icon: LayoutGrid },
        { href: "/portfolio", label: "Portfolio", icon: PieChart },
        { href: "/risk", label: "Risk", icon: ShieldCheck },
      ]} />

      <PageHeader
        eyebrow="Overview"
        title="Trading Dashboard"
        badge={
          <StatusChip
            variant={mode === "live" ? "live" : "paper"}
            label={mode === "live" ? "LIVE MODE" : "PAPER MODE"}
            pulse
          />
        }
        meta={
          lastRefresh ? (
            <span className="app-pill font-mono tracking-normal flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-alive-pulse" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          ) : undefined
        }
        actions={
          <button onClick={fetchAll} className="app-button-secondary">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </button>
        }
      />

      {/* ── ZONE 2: METRICS + MARKET INTEL ─────────────────────────── */}
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

      <MarketIntelligenceBar
        trend={{ direction: "bullish", label: "Bullish" }}
        volatility={{ vix: 16.4, level: "low" }}
        sentiment="risk-on"
        bestSector="Technology"
        strategyStatus={{ active: positions.length > 0, name: "AI Momentum" }}
      />

      {/* ── ZONE 3: PRIMARY CHART ──────────────────────────────────── */}
      <section className="dashboard-chart-hero">
        <DashboardPanel title="Portfolio Equity" icon={TrendingUp} noPadding>
          <PortfolioEquityChart height={440} />
        </DashboardPanel>
        <CerberusInsightChip />
      </section>

      {/* ═══════════════════════════════════════════════════════════════
          CONTROL SURFACE — grouped operational zones, scan-first
          ═══════════════════════════════════════════════════════════════ */}

      {/* ── ZONE 4: AI + STRATEGY (tabbed) | RISK + ANALYTICS (tabbed) ── */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">

        {/* LEFT: Strategy & AI Intelligence */}
        <Section title="Strategy & Intelligence" icon={Brain} defaultOpen>
          <TabBar
            tabs={[
              { key: "reasoning", label: "AI Reasoning", icon: Brain },
              { key: "scanner", label: "Scanner", icon: Crosshair },
              { key: "strategy", label: "Strategies", icon: Zap },
            ]}
            active={aiTab}
            onChange={setAiTab}
          />
          <div className="app-panel overflow-hidden">
            <div className="p-4">
              {aiTab === "reasoning" && <AIReasoningPanel decision={null} />}
              {aiTab === "scanner" && <AIScannerPanel totalWatching={0} signals={[]} />}
              {aiTab === "strategy" && <StrategyPanel strategies={[]} />}
            </div>
          </div>
        </Section>

        {/* RIGHT: Risk & Market */}
        <Section title="Risk & Market" icon={ShieldCheck} defaultOpen>
          <TabBar
            tabs={[
              { key: "metrics", label: "Risk Metrics", icon: ShieldCheck },
              { key: "sentiment", label: "Sentiment", icon: Activity },
              { key: "exposure", label: "Exposure", icon: Target },
            ]}
            active={riskTab}
            onChange={setRiskTab}
          />
          <div className="app-panel overflow-hidden">
            <div className="p-4">
              {riskTab === "metrics" && (
                <RiskMetricsPanel
                  winRate={winRate ?? undefined}
                  maxDrawdown={risk?.current_drawdown_pct ?? 0}
                  totalTrades={filledOrderCount}
                />
              )}
              {riskTab === "sentiment" && <MarketMoodWidget />}
              {riskTab === "exposure" && (
                <PortfolioRiskDashPanel
                  totalExposure={risk?.current_exposure_pct ?? 0}
                />
              )}
            </div>
          </div>
        </Section>
      </div>

      {/* ── ZONE 5: EXECUTION SURFACE ──────────────────────────────── */}
      <Section title="Execution" icon={Radio} defaultOpen>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1fr]">
          <div className="app-panel overflow-hidden">
            <div className="flex items-center gap-2 border-b border-border/40 px-4 py-2.5">
              <Target className="h-3.5 w-3.5 text-muted-foreground/60" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Open Positions
              </span>
              <span className="rounded-full bg-muted/50 px-1.5 py-0.5 text-[9px] font-mono text-muted-foreground">
                {positions.length}
              </span>
            </div>
            <OpenPositionsPanel positions={positions} />
          </div>

          <div className="app-panel overflow-hidden">
            <div className="flex items-center justify-between border-b border-border/40 px-4 py-2.5">
              <div className="flex items-center gap-2">
                <Receipt className="h-3.5 w-3.5 text-muted-foreground/60" />
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Trade Log
                </span>
                <span className="rounded-full bg-muted/50 px-1.5 py-0.5 text-[9px] font-mono text-muted-foreground">
                  {orders.length}
                </span>
              </div>
              <button
                type="button"
                onClick={fetchAll}
                className="text-muted-foreground/40 hover:text-muted-foreground transition-colors"
              >
                <RefreshCw className="h-3 w-3" />
              </button>
            </div>
            <TradeLogPanel orders={orders} />
          </div>
        </div>
      </Section>

      {/* ── ZONE 6: SECONDARY ANALYTICS (collapsed by default) ───── */}
      <Section title="Analytics" icon={TrendingUp} defaultOpen={false}>
        <div className="app-panel overflow-hidden">
          <div className="p-4">
            <EquityCurvePanel data={equityCurve} />
          </div>
        </div>
      </Section>
    </div>
  );
}
