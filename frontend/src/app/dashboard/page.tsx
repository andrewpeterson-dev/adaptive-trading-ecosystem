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
import { SubNav } from "@/components/layout/SubNav";
import {
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
// Collapsible Zone — compact control-surface building block
// ---------------------------------------------------------------------------

function Zone({
  title,
  icon: Icon,
  children,
  defaultOpen = true,
  count,
}: {
  title: string;
  icon: React.ElementType;
  children: React.ReactNode;
  defaultOpen?: boolean;
  count?: number;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <section>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-2 py-1.5 group"
      >
        <Icon className="h-3 w-3 text-muted-foreground/50" />
        <span className="text-[9px] font-semibold uppercase tracking-[0.22em] text-muted-foreground/60">
          {title}
        </span>
        {count != null && (
          <span className="text-[9px] font-mono text-muted-foreground/40">{count}</span>
        )}
        <span className="flex-1 border-b border-border/20 ml-2" />
        <ChevronDown
          className={cn(
            "h-3 w-3 text-muted-foreground/30 transition-transform duration-200",
            !open && "-rotate-90"
          )}
        />
      </button>
      <div
        className={cn(
          "grid transition-[grid-template-rows] duration-250 ease-out",
          open ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
        )}
      >
        <div className="overflow-hidden">
          <div className="pt-2">{children}</div>
        </div>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Compact Tab Selector
// ---------------------------------------------------------------------------

function Tabs({
  items,
  active,
  onChange,
}: {
  items: { key: string; label: string }[];
  active: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex items-center gap-px mb-2">
      {items.map((item) => (
        <button
          key={item.key}
          type="button"
          onClick={() => onChange(item.key)}
          className={cn(
            "px-3 py-1 text-[10px] font-semibold transition-all duration-150 first:rounded-l-md last:rounded-r-md",
            active === item.key
              ? "bg-foreground/10 text-foreground"
              : "text-muted-foreground/50 hover:text-muted-foreground hover:bg-foreground/[0.03]"
          )}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Cerberus Chip
// ---------------------------------------------------------------------------

function CerberusChip() {
  return (
    <div className="flex items-center gap-3 ml-auto w-fit rounded-full border border-border/30 cerberus-chip px-3.5 py-1.5 mt-2">
      <div className="signal-bars flex items-end gap-[2px]">
        <span className="block h-[5px] w-[2px] rounded-full bg-emerald-400/70" />
        <span className="block h-[8px] w-[2px] rounded-full bg-emerald-400/50" />
        <span className="block h-[11px] w-[2px] rounded-full bg-emerald-400/35" />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground/50">
        Cerberus &bull; Structure stable &bull; Regime: Normal
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Mini Panel Header — for inline panel titles without DashboardPanel wrapper
// ---------------------------------------------------------------------------

function PanelHeader({
  icon: Icon,
  title,
  count,
  action,
}: {
  icon: React.ElementType;
  title: string;
  count?: number;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex items-center justify-between border-b border-border/30 px-3 py-2">
      <div className="flex items-center gap-1.5">
        <Icon className="h-3 w-3 text-muted-foreground/50" />
        <span className="text-[9px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/70">
          {title}
        </span>
        {count != null && (
          <span className="rounded-full bg-muted/40 px-1.5 py-px text-[8px] font-mono text-muted-foreground/50">
            {count}
          </span>
        )}
      </div>
      {action}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [equityCurve, setEquityCurve] = useState<{ date: string; equity: number; drawdown: number }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const { mode } = useTradingMode();

  const [aiTab, setAiTab] = useState("reasoning");
  const [riskTab, setRiskTab] = useState("metrics");

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

      if (accRes.status === "fulfilled") { setAccount(accRes.value); setError(false); } else { setError(true); }
      if (posRes.status === "fulfilled") setPositions(posRes.value.positions || []);
      if (ordRes.status === "fulfilled") setOrders(ordRes.value.orders || []);
      if (riskRes.status === "fulfilled") setRisk(riskRes.value);
      if (eqRes.status === "fulfilled") {
        const eqData = eqRes.value;
        setEquityCurve(eqData.equity_curve || eqData || []);
      }
      setLastRefresh(new Date());
    } catch { setError(true); } finally { setLoading(false); }
  }, [mode]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const totalPnl = useMemo(() => positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0), [positions]);
  const filledOrderCount = useMemo(() => orders.filter((o) => o.status === "filled").length, [orders]);
  const winRate = useMemo(() => filledOrderCount === 0 ? null : null, [filledOrderCount]);

  // -- Early returns --
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
        <SubNav items={[{ href: "/dashboard", label: "Overview", icon: LayoutGrid }, { href: "/portfolio", label: "Portfolio", icon: PieChart }, { href: "/risk", label: "Risk", icon: ShieldCheck }]} />
        <EmptyState icon={<Unplug className="h-6 w-6 text-amber-400" />} title="No live trading configured" description={account.message || "Connect a live API key in Settings."} action={<Link href="/settings" className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"><Settings className="h-4 w-4" />Settings</Link>} />
      </div>
    );
  }

  if (error && !account) {
    return (
      <div className="app-page">
        <SubNav items={[{ href: "/dashboard", label: "Overview", icon: LayoutGrid }, { href: "/portfolio", label: "Portfolio", icon: PieChart }, { href: "/risk", label: "Risk", icon: ShieldCheck }]} />
        <EmptyState icon={<Unplug className="h-6 w-6 text-muted-foreground/60" />} title="Broker not responding" description="Could not load account data." action={<button onClick={fetchAll} className="inline-flex items-center gap-2 rounded-lg border border-border/60 bg-secondary px-4 py-2 text-sm font-medium hover:bg-secondary/80 transition-colors"><RefreshCw className="h-4 w-4" />Retry</button>} />
      </div>
    );
  }

  // =========================================================================
  // MAIN DASHBOARD — scan-first control surface
  // =========================================================================

  return (
    <div className="space-y-3 pb-8 relative">
      <AmbientBackground />

      {/* ── SYSTEM STATE ──────────────────────────────────────────── */}
      <SubNav items={[
        { href: "/dashboard", label: "Overview", icon: LayoutGrid },
        { href: "/portfolio", label: "Portfolio", icon: PieChart },
        { href: "/risk", label: "Risk", icon: ShieldCheck },
      ]} />

      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold tracking-tight">Dashboard</h1>
          <StatusChip
            variant={mode === "live" ? "live" : "paper"}
            label={mode === "live" ? "LIVE" : "PAPER"}
            pulse
          />
          {lastRefresh && (
            <span className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground/50">
              <span className="h-1 w-1 rounded-full bg-emerald-400 animate-alive-pulse" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
        </div>
        <button onClick={fetchAll} className="app-button-secondary !py-1.5 !px-3 !text-xs">
          <RefreshCw className="h-3 w-3" />
          Refresh
        </button>
      </div>

      {/* ── METRICS ───────────────────────────────────────────────── */}
      <MetricsRow
        totalPnl={totalPnl}
        unrealizedPnl={totalPnl}
        realizedPnl={0}
        expectancy={0}
        winRate={winRate ?? 0}
        maxDrawdown={risk?.current_drawdown_pct ?? 0}
        exposure={risk?.current_exposure_pct ?? 0}
        tradesToday={risk?.trades_this_hour ?? 0}
        tradeHistory={[]}
        realizedPnlUnavailable
        winRateUnavailable={!winRate}
      />

      <MarketIntelligenceBar
        trend={{ direction: "bullish", label: "Bullish" }}
        volatility={{ vix: 16.4, level: "low" }}
        sentiment="risk-on"
        bestSector="Technology"
        strategyStatus={{ active: positions.length > 0, name: "AI Momentum" }}
      />

      {/* ── PRIMARY CHART ─────────────────────────────────────────── */}
      <section className="dashboard-chart-hero">
        <div className="app-panel overflow-hidden">
          <PortfolioEquityChart height={400} />
        </div>
        <CerberusChip />
      </section>

      {/* ═══════════════════════════════════════════════════════════
          CONTROL SURFACE — grouped operational zones
          ═══════════════════════════════════════════════════════════ */}

      {/* ── INTELLIGENCE + RISK — 2-column tabbed ─────────────────── */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {/* Strategy & AI */}
        <Zone title="Intelligence" icon={Brain}>
          <div className="app-panel overflow-hidden">
            <div className="px-3 pt-3 pb-0">
              <Tabs
                items={[
                  { key: "reasoning", label: "AI Reasoning" },
                  { key: "scanner", label: "Scanner" },
                  { key: "strategy", label: "Strategies" },
                ]}
                active={aiTab}
                onChange={setAiTab}
              />
            </div>
            <div className="p-3">
              {aiTab === "reasoning" && <AIReasoningPanel decision={null} />}
              {aiTab === "scanner" && <AIScannerPanel totalWatching={0} signals={[]} />}
              {aiTab === "strategy" && <StrategyPanel strategies={[]} />}
            </div>
          </div>
        </Zone>

        {/* Risk & Market */}
        <Zone title="Risk & Market" icon={ShieldCheck}>
          <div className="app-panel overflow-hidden">
            <div className="px-3 pt-3 pb-0">
              <Tabs
                items={[
                  { key: "metrics", label: "Risk" },
                  { key: "sentiment", label: "Sentiment" },
                  { key: "exposure", label: "Exposure" },
                ]}
                active={riskTab}
                onChange={setRiskTab}
              />
            </div>
            <div className="p-3">
              {riskTab === "metrics" && (
                <RiskMetricsPanel
                  winRate={winRate ?? undefined}
                  maxDrawdown={risk?.current_drawdown_pct ?? 0}
                  totalTrades={filledOrderCount}
                />
              )}
              {riskTab === "sentiment" && <MarketMoodWidget />}
              {riskTab === "exposure" && (
                <PortfolioRiskDashPanel totalExposure={risk?.current_exposure_pct ?? 0} />
              )}
            </div>
          </div>
        </Zone>
      </div>

      {/* ── EXECUTION — positions + trade log side by side ─────────── */}
      <Zone title="Execution" icon={Radio} count={positions.length + orders.length}>
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <div className="app-panel overflow-hidden">
            <PanelHeader icon={Target} title="Positions" count={positions.length} />
            <OpenPositionsPanel positions={positions} />
          </div>
          <div className="app-panel overflow-hidden">
            <PanelHeader
              icon={Receipt}
              title="Trade Log"
              count={orders.length}
              action={
                <button type="button" onClick={fetchAll} className="text-muted-foreground/30 hover:text-muted-foreground transition-colors">
                  <RefreshCw className="h-2.5 w-2.5" />
                </button>
              }
            />
            <TradeLogPanel orders={orders} />
          </div>
        </div>
      </Zone>

      {/* ── ANALYTICS — collapsed by default ──────────────────────── */}
      <Zone title="Analytics" icon={TrendingUp} defaultOpen={false}>
        <div className="app-panel overflow-hidden p-3">
          <EquityCurvePanel data={equityCurve} />
        </div>
      </Zone>
    </div>
  );
}
