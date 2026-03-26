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
  PaperModeBanner,
} from "@/components/dashboard";
import { PortfolioEquityChart } from "@/components/dashboard/PortfolioEquityChart";
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
        className="flex w-full items-center gap-2.5 rounded-lg border border-border/40 bg-muted/8 px-3.5 py-2.5 transition-colors hover:bg-muted/15 hover:border-border/60 group"
      >
        <Icon className="h-3.5 w-3.5 text-muted-foreground/60" />
        <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground/80">
          {title}
        </span>
        {count != null && (
          <span className="rounded-full bg-muted/40 px-1.5 py-px text-[9px] font-mono text-muted-foreground/50">{count}</span>
        )}
        <span className="flex-1" />
        <ChevronDown
          className={cn(
            "h-3.5 w-3.5 text-muted-foreground/40 transition-transform duration-200",
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

function CerberusChip({ mode, isHalted, activeBots }: { mode: string; isHalted: boolean; activeBots: number }) {
  const statusLabel = isHalted ? "Halted" : activeBots > 0 ? `${activeBots} bot${activeBots !== 1 ? "s" : ""} active` : "Idle";
  const statusColor = isHalted ? "bg-red-400/70" : activeBots > 0 ? "bg-emerald-400/70" : "bg-amber-400/50";

  return (
    <div className="flex items-center gap-3 ml-auto w-fit rounded-full border border-border/30 cerberus-chip px-3.5 py-1.5 mt-2">
      <div className="signal-bars flex items-end gap-[2px]">
        <span className={`block h-[5px] w-[2px] rounded-full ${statusColor}`} />
        <span className={`block h-[8px] w-[2px] rounded-full ${statusColor} opacity-70`} />
        <span className={`block h-[11px] w-[2px] rounded-full ${statusColor} opacity-50`} />
      </div>
      <span className="text-[10px] font-mono text-muted-foreground/50">
        Cerberus &bull; {mode === "live" ? "Live" : "Paper"} &bull; {statusLabel}
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

// ---------------------------------------------------------------------------
// Market intelligence types
// ---------------------------------------------------------------------------

interface MarketMoodData {
  market_mood: "bullish" | "bearish" | "neutral";
  score: number;
  confidence: number;
}

interface BotSummaryData {
  id: string;
  name: string;
  status: string;
}

export default function DashboardPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [risk, setRisk] = useState<RiskSummary | null>(null);
  const [equityCurve, setEquityCurve] = useState<{ date: string; equity: number; drawdown: number }[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [marketMood, setMarketMood] = useState<MarketMoodData | null>(null);
  const [bots, setBots] = useState<BotSummaryData[]>([]);
  const [strategies, setStrategies] = useState<{ id: string; name: string; status: "active" | "paused" | "backtesting"; mode: "paper" | "live"; winRate?: number; trades?: number; pnl?: number }[]>([]);
  const [latestDecision, setLatestDecision] = useState<any>(null);
  const [tradeHistory, setTradeHistory] = useState<number[]>([]);
  const { mode } = useTradingMode();

  const [aiTab, setAiTab] = useState("reasoning");
  const [riskTab, setRiskTab] = useState("metrics");

  const fetchAll = useCallback(async () => {
    // Hard timeout: exit loading state after 10s regardless of pending requests
    const loadingTimeout = new Promise<void>((resolve) => setTimeout(resolve, 10_000));

    try {
      const q = `?mode=${mode}`;
      const fetchPromise = Promise.allSettled([
        apiFetch<Account>(`/api/trading/account${q}`),
        apiFetch<{ positions: Position[] }>(`/api/trading/positions${q}`),
        apiFetch<{ orders: Order[] }>(`/api/trading/orders${q}`),
        apiFetch<RiskSummary>(`/api/trading/risk-summary${q}`),
        apiFetch<any>(`/api/dashboard/equity-curve${q}`),
        apiFetch<MarketMoodData>(`/api/sentiment/market-mood/overview`),
        apiFetch<BotSummaryData[]>(`/api/ai/tools/bots`),
        apiFetch<{ strategies: any[] } | any[]>(`/api/strategies/list`),
        apiFetch<any>(`/api/reasoning/latest`),
      ]);

      // Race: either all settle or 10s passes — either way, exit loading state
      const raceResult = await Promise.race([
        fetchPromise.then((results) => ({ settled: true as const, results })),
        loadingTimeout.then(() => ({ settled: false as const })),
      ]);

      if (!raceResult.settled) {
        // Timed out — exit loading with whatever partial data we have
        return;
      }

      const [accRes, posRes, ordRes, riskRes, eqRes, moodRes, botsRes, stratRes, decisionRes] = raceResult.results;

      if (accRes.status === "fulfilled") { setAccount(accRes.value); setError(false); } else { setError(true); }
      if (posRes.status === "fulfilled") setPositions(posRes.value.positions || []);
      if (ordRes.status === "fulfilled") {
        const allOrders = ordRes.value.orders || [];
        setOrders(allOrders);
        // Build trade sparkline from recent filled orders (last 24 values)
        const filled = allOrders.filter((o: Order) => o.status === "filled" && o.filled_price != null);
        setTradeHistory(filled.slice(-24).map((o: Order) => o.filled_price ?? 0));
      }
      if (riskRes.status === "fulfilled") setRisk(riskRes.value);
      if (eqRes.status === "fulfilled") {
        const eqData = eqRes.value;
        setEquityCurve(Array.isArray(eqData?.equity_curve) ? eqData.equity_curve : Array.isArray(eqData) ? eqData : []);
      }
      if (moodRes.status === "fulfilled") setMarketMood(moodRes.value);
      if (botsRes.status === "fulfilled") setBots(botsRes.value || []);
      if (stratRes.status === "fulfilled") {
        const val = stratRes.value;
        const raw = Array.isArray(val) ? val : Array.isArray((val as any)?.strategies) ? (val as any).strategies : [];
        setStrategies(raw.map((s: any) => ({
          id: String(s.id),
          name: s.name || "Unnamed",
          status: (s.is_active === false ? "paused" : "active") as "active" | "paused",
          mode: mode as "paper" | "live",
          winRate: s.win_rate,
          trades: s.num_trades,
          pnl: s.total_pnl,
        })));
      }
      if (decisionRes.status === "fulfilled" && decisionRes.value) {
        setLatestDecision(decisionRes.value);
      }
      setLastRefresh(new Date());
    } catch { setError(true); } finally { setInitialLoading(false); }
  }, [mode]);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const initialCapital = account?.initial_capital ?? 100_000;

  const totalPnl = useMemo(() => {
    if (account) {
      return (account.equity || 0) - initialCapital;
    }
    return positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0);
  }, [account, positions, initialCapital]);

  const unrealizedPnl = useMemo(
    () => account?.unrealized_pnl ?? positions.reduce((sum, p) => sum + (p.unrealized_pnl ?? 0), 0),
    [account, positions],
  );

  const realizedPnl = useMemo(
    () => account?.realized_pnl ?? (totalPnl - unrealizedPnl),
    [account, totalPnl, unrealizedPnl],
  );

  const filledOrderCount = useMemo(() => orders.filter((o) => o.status === "filled").length, [orders]);

  const winRate = useMemo(() => {
    const filled = orders.filter((o) => o.status === "filled" && o.filled_price != null);
    if (filled.length === 0) return null;
    // Count buy orders that later had profitable sells (simplified: use P&L from positions)
    const profitable = positions.filter((p) => (p.unrealized_pnl ?? 0) > 0).length;
    const total = positions.length;
    return total > 0 ? (profitable / total) * 100 : null;
  }, [orders, positions]);

  // Derive market intelligence from live data
  const activeBots = useMemo(() => bots.filter((b) => b.status === "running"), [bots]);
  const marketIntel = useMemo(() => {
    const mood = marketMood?.market_mood ?? "neutral";
    const score = marketMood?.score ?? 0;
    const direction = mood === "bullish" ? "bullish" as const
      : mood === "bearish" ? "bearish" as const
      : "sideways" as const;
    const sentiment = score > 0.1 ? "risk-on" as const
      : score < -0.1 ? "risk-off" as const
      : "neutral" as const;
    return { direction, sentiment, label: mood.charAt(0).toUpperCase() + mood.slice(1) };
  }, [marketMood]);

  // -- Early returns --
  if (initialLoading) {
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

      {/* ── PAPER PORTFOLIO (only visible in paper mode) ──────────── */}
      <PaperModeBanner />

      {/* ── METRICS ───────────────────────────────────────────────── */}
      <MetricsRow
        totalPnl={totalPnl}
        unrealizedPnl={unrealizedPnl}
        realizedPnl={realizedPnl}
        expectancy={filledOrderCount > 0 ? totalPnl / filledOrderCount : 0}
        winRate={winRate ?? 0}
        maxDrawdown={risk?.current_drawdown_pct ?? 0}
        exposure={account ? (account.portfolio_value || 0) / (account.equity || 1) : 0}
        tradesToday={risk?.trades_this_hour ?? 0}
        tradeHistory={tradeHistory}
        realizedPnlUnavailable={!account?.realized_pnl && account?.realized_pnl !== 0}
        winRateUnavailable={winRate === null}
      />

      <MarketIntelligenceBar
        trend={{ direction: marketIntel.direction, label: marketIntel.label }}
        volatility={undefined}
        sentiment={marketIntel.sentiment}
        bestSector={undefined}
        strategyStatus={{
          active: activeBots.length > 0,
          name: activeBots.length > 0 ? `${activeBots.length} bots active` : undefined,
        }}
      />

      {/* ── PRIMARY CHART ─────────────────────────────────────────── */}
      <section className="dashboard-chart-hero">
        <div className="app-panel" style={{ minHeight: 480, overflow: "visible" }}>
          <PortfolioEquityChart height={400} />
        </div>
        <CerberusChip mode={mode} isHalted={risk?.is_halted ?? false} activeBots={activeBots.length} />
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
              {aiTab === "reasoning" && <AIReasoningPanel decision={latestDecision} />}
              {aiTab === "scanner" && <AIScannerPanel totalWatching={bots.length} />}
              {aiTab === "strategy" && <StrategyPanel strategies={strategies} />}
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
                <PortfolioRiskDashPanel
                  totalExposure={risk?.current_exposure_pct ?? 0}
                  riskBudgetUsed={risk ? (risk.current_drawdown_pct / (risk.max_drawdown_limit_pct || 1)) : undefined}
                />
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
            <OpenPositionsPanel positions={positions} hideHeader />
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
            <TradeLogPanel orders={orders} hideHeader />
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
