"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Brain, GraduationCap, Globe, LineChart } from "lucide-react";

import { Skeleton } from "@/components/ui/skeleton";
import { AIReasoningTab } from "@/components/bots/reasoning/AIReasoningTab";
import { LearningTab } from "@/components/bots/reasoning/LearningTab";
import { UniverseTab } from "@/components/bots/reasoning/UniverseTab";
import { cn } from "@/lib/utils";
import { getBotDetail, type BotDetail, type BotTrade } from "@/lib/cerberus-api";
import {
  filterTradesBySymbol,
  formatTimeframe,
  getBotConfig,
  getTrackedSymbols,
  getTradeById,
  summarizeRisk,
  type TimelineGranularity,
} from "@/lib/bot-visualization";

// Terminal panels
import { DashboardLayout } from "@/components/terminal/DashboardLayout";
import { TerminalPanel } from "@/components/terminal/TerminalPanel";
import { PerformanceMetricsPanel } from "@/components/terminal/PerformanceMetricsPanel";
import { OpenPositionsPanel } from "@/components/terminal/OpenPositionsPanel";
import { RiskMetricsPanel } from "@/components/terminal/RiskMetricsPanel";
import { StrategySettingsPanel } from "@/components/terminal/StrategySettingsPanel";
import { EntryLogicPanel } from "@/components/terminal/EntryLogicPanel";
import { UniversePanel } from "@/components/terminal/UniversePanel";
import { CapitalPanel } from "@/components/terminal/CapitalPanel";
import { TradeLogPanel } from "@/components/terminal/TradeLogPanel";
import { AIReasoningPanel } from "@/components/terminal/AIReasoningPanel";
import { ChartPanel } from "@/components/terminal/ChartPanel";
import { MarketContextPanel } from "@/components/terminal/MarketContextPanel";
import { MarketScannerPanel } from "@/components/terminal/MarketScannerPanel";
import { TradeInspectorModal } from "@/components/terminal/TradeInspectorModal";

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function BotDetailPage() {
  const params = useParams<{ id?: string | string[] }>();
  const botId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "";

  const [detail, setDetail] = useState<BotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSymbol, setActiveSymbol] = useState<string>("");
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [hoveredTradeId, setHoveredTradeId] = useState<string | null>(null);
  const [inspectedTrade, setInspectedTrade] = useState<BotTrade | null>(null);
  const [activeTab, setActiveTab] = useState<"terminal" | "reasoning" | "learning" | "universe">("terminal");

  useEffect(() => {
    async function load() {
      try {
        const data = await getBotDetail(botId);
        setDetail(data);
        setError(null);
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Failed to load bot detail");
      } finally {
        setLoading(false);
      }
    }
    if (botId) void load();
  }, [botId]);

  const trackedSymbols = useMemo(
    () => (detail ? getTrackedSymbols(detail) : []),
    [detail],
  );

  useEffect(() => {
    if (!detail) return;
    const tradedSymbol = detail.trades.length > 0
      ? detail.trades.reduce((best, t) => {
          const counts: Record<string, number> = {};
          detail.trades.forEach(tr => { counts[tr.symbol] = (counts[tr.symbol] || 0) + 1; });
          return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] || best;
        }, detail.primarySymbol)
      : null;
    const fallback = tradedSymbol || detail.primarySymbol || trackedSymbols[0] || "SPY";
    setActiveSymbol((current) => (current && trackedSymbols.includes(current) ? current : fallback));
  }, [detail, trackedSymbols]);

  const symbolTrades = useMemo(
    () => (detail ? filterTradesBySymbol(detail.trades, activeSymbol || detail.primarySymbol || "SPY") : []),
    [detail, activeSymbol],
  );

  const selectedTrade = useMemo(
    () => getTradeById(symbolTrades, selectedTradeId) ?? getTradeById(detail?.trades ?? [], selectedTradeId),
    [selectedTradeId, symbolTrades, detail],
  );

  const hoveredTrade = useMemo(
    () => getTradeById(symbolTrades, hoveredTradeId),
    [hoveredTradeId, symbolTrades],
  );

  const handleSelectTrade = (trade: BotTrade) => {
    setActiveSymbol(trade.symbol.toUpperCase());
    setSelectedTradeId(trade.id);
    setInspectedTrade(trade);
  };

  // Loading state
  if (loading) {
    return (
      <div className="app-page">
        <Skeleton className="h-16 rounded-2xl" />
        <div className="grid grid-cols-4 gap-3 mt-3">
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-32 rounded-2xl" />)}
        </div>
      </div>
    );
  }

  if (!detail || error) {
    return (
      <div className="app-page">
        <div className="rounded-2xl border border-rose-400/20 bg-rose-400/5 p-6 text-rose-400">
          {error || "Bot detail is unavailable."}
        </div>
      </div>
    );
  }

  const config = getBotConfig(detail);
  const riskSummary = summarizeRisk(config);
  const perf = detail.performance;
  const totalPnl = (perf.realized_pnl ?? 0) + (perf.unrealized_pnl ?? 0);
  const openPositionSymbols = (perf.open_positions ?? []).map(p => p.symbol);

  return (
    <div className="app-page">
      {/* ── Sticky Header ─────────────────────────────────────────── */}
      <div className="sticky top-0 z-30 -mx-4 px-4 pt-2 pb-3 bg-background/80 backdrop-blur-xl border-b border-border/30">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/bots" className="rounded-lg border border-border/50 p-1.5 text-muted-foreground hover:text-foreground hover:border-border transition-colors">
              <ArrowLeft className="h-4 w-4" />
            </Link>
            <div className="min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <h1 className="text-lg font-bold text-foreground truncate">{detail.name}</h1>
                <span className={`inline-flex items-center gap-1 rounded-full px-2.5 py-0.5 text-[10px] font-bold uppercase tracking-wider ${
                  detail.status === "running" ? "bg-emerald-400/15 text-emerald-400" :
                  detail.status === "paused" ? "bg-amber-400/15 text-amber-400" :
                  "bg-muted/30 text-muted-foreground"
                }`}>
                  {detail.status === "running" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />}
                  {detail.status}
                </span>
                <span className="app-pill font-mono text-[10px]">{formatTimeframe(config.timeframe)}</span>
                <span className="app-pill font-mono text-[10px]">{riskSummary}</span>
              </div>
              <div className="text-[11px] text-muted-foreground mt-0.5 truncate">
                {detail.overview || "No strategy description"}
              </div>
            </div>
          </div>

          {/* P&L hero metric */}
          <div className="text-right shrink-0">
            <div className={`text-2xl font-bold font-mono ${totalPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {(perf.open_count ?? 0)} open &middot; {(perf.closed_count ?? 0)} closed
            </div>
          </div>
        </div>

        {/* Tab navigation */}
        <div className="flex items-center gap-1 mt-3">
          {([
            { key: "terminal" as const, label: "Terminal", icon: LineChart },
            { key: "reasoning" as const, label: "AI Reasoning", icon: Brain },
            { key: "learning" as const, label: "Learning", icon: GraduationCap },
            { key: "universe" as const, label: "Universe", icon: Globe },
          ]).map(({ key, label, icon: Icon }) => (
            <button
              key={key}
              onClick={() => setActiveTab(key)}
              className={cn(
                "flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all",
                activeTab === key
                  ? "bg-primary/12 text-primary border border-primary/20"
                  : "text-muted-foreground hover:bg-muted/30 hover:text-foreground"
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* ── Tab Content ───────────────────────────────────────────── */}
      {activeTab === "reasoning" && <AIReasoningTab botId={botId} />}
      {activeTab === "learning" && <LearningTab botId={botId} />}
      {activeTab === "universe" && <UniverseTab botId={botId} />}

      {activeTab === "terminal" && (
        <div className="mt-3">
          <DashboardLayout>
            {{
              performance: (
                <PerformanceMetricsPanel detail={detail} />
              ),
              capital: (
                <CapitalPanel
                  detail={detail}
                  onDetailUpdate={(updates) => setDetail(prev => prev ? { ...prev, ...updates } : prev)}
                />
              ),
              settings: (
                <StrategySettingsPanel config={config} strategyType={detail.strategyType} />
              ),
              chart: (
                <ChartPanel
                  symbol={activeSymbol}
                  trades={symbolTrades}
                  selectedTrade={selectedTrade}
                  hoveredTrade={hoveredTrade}
                  selectedTradeId={selectedTradeId}
                  onHoverTrade={setHoveredTradeId}
                  onSelectTrade={setSelectedTradeId}
                  equityCurve={detail.equityCurve}
                  initialCapital={detail.allocatedCapital ?? 100000}
                />
              ),
              positions: (
                <OpenPositionsPanel
                  performance={detail.performance}
                  onSelectSymbol={(sym) => { setActiveSymbol(sym); setSelectedTradeId(null); }}
                />
              ),
              risk: (
                <RiskMetricsPanel config={config} />
              ),
              logic: (
                <EntryLogicPanel
                  conditions={(Array.isArray(config.conditions) ? config.conditions : []) as Array<Record<string, unknown>>}
                  exitConditions={(Array.isArray(config.exit_conditions) ? config.exit_conditions : Array.isArray((config.ai_context as Record<string, unknown>)?.exit_conditions) ? (config.ai_context as Record<string, unknown>).exit_conditions : []) as Array<Record<string, unknown>>}
                  stopLossPct={config.stop_loss_pct as number | undefined}
                  takeProfitPct={config.take_profit_pct as number | undefined}
                />
              ),
              universe: (
                <UniversePanel
                  symbols={trackedSymbols}
                  activeSymbol={activeSymbol}
                  onSymbolSelect={(sym) => { setActiveSymbol(sym); setSelectedTradeId(null); setHoveredTradeId(null); }}
                  openPositionSymbols={openPositionSymbols}
                />
              ),
              tradelog: (
                <TradeLogPanel
                  trades={detail.trades}
                  selectedTradeId={selectedTradeId}
                  onSelectTrade={handleSelectTrade}
                />
              ),
              ai_decision: (
                <AIReasoningPanel detail={detail} trade={selectedTrade} />
              ),
              market: (
                <MarketContextPanel detail={detail} />
              ),
              scanner: (
                <MarketScannerPanel
                  symbols={trackedSymbols}
                  trades={detail.trades}
                  conditions={(Array.isArray(config.conditions) ? config.conditions : []) as Array<Record<string, unknown>>}
                />
              ),
            }}
          </DashboardLayout>
        </div>
      )}

      {/* Trade Inspector Modal */}
      <TradeInspectorModal
        trade={inspectedTrade}
        config={config}
        onClose={() => setInspectedTrade(null)}
      />
    </div>
  );
}
