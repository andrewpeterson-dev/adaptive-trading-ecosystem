"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Brain, GraduationCap, Globe, LineChart, Cpu, Zap } from "lucide-react";

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
} from "@/lib/bot-visualization";

// Terminal panels
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
import { ModelLeaderboard } from "@/components/bots/ModelLeaderboard";
import { BotModelSettings } from "@/components/bots/BotModelSettings";
import { LiveDecisionFeed } from "@/components/bots/LiveDecisionFeed";
import { apiFetch } from "@/lib/api/client";

function EnableAIBrainCTA({ botId, onEnabled }: { botId: string; onEnabled: () => void }) {
  const [enabling, setEnabling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleEnable = async () => {
    setEnabling(true);
    setError(null);
    try {
      await apiFetch(`/api/ai/tools/bots/${botId}/ai-config`, {
        method: "PATCH",
        body: JSON.stringify({
          execution_mode: "ai_assisted",
          model_config: { primary_model: "gpt-5.4" },
          data_sources: ["technical", "sentiment"],
        }),
      });
      onEnabled();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to enable AI Brain");
    } finally {
      setEnabling(false);
    }
  };

  return (
    <div className="app-panel p-5 flex items-center justify-between gap-4">
      <div className="flex items-center gap-3 min-w-0">
        <div className="shrink-0 rounded-xl bg-violet-500/10 p-2.5">
          <Cpu className="h-5 w-5 text-violet-400" />
        </div>
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-foreground">AI Brain</h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Let AI analyze markets and assist with trading decisions for this bot
          </p>
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {error && <span className="text-[11px] text-red-400">{error}</span>}
        <button
          onClick={handleEnable}
          disabled={enabling}
          className="flex items-center gap-1.5 rounded-xl bg-violet-500/15 border border-violet-500/25 px-4 py-2 text-xs font-semibold text-violet-400 hover:bg-violet-500/25 transition-colors disabled:opacity-50"
        >
          <Zap className="h-3.5 w-3.5" />
          {enabling ? "Enabling..." : "Enable"}
        </button>
      </div>
    </div>
  );
}

export default function BotDetailPage() {
  const params = useParams<{ id: string }>();
  const botId = params?.id ?? "";

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
    // Auto-refresh every 30s to keep terminal data current with server-side bot updates
    const interval = setInterval(() => { if (botId) void load(); }, 30_000);
    return () => clearInterval(interval);
  }, [botId]);

  const trackedSymbols = useMemo(() => (detail ? getTrackedSymbols(detail) : []), [detail]);

  useEffect(() => {
    if (!detail) return;
    const tradedSymbol = detail.trades.length > 0
      ? (() => {
          const counts: Record<string, number> = {};
          detail.trades.forEach(tr => { counts[tr.symbol] = (counts[tr.symbol] || 0) + 1; });
          return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? null;
        })()
      : null;
    const fallback = tradedSymbol || detail.primarySymbol || trackedSymbols[0] || "";
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
      <div className="sticky top-0 z-30 -mx-4 px-4 pt-2 pb-3 bg-background/90 backdrop-blur-xl border-b border-border/30">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 min-w-0">
            <Link href="/bots" className="rounded-lg border border-border/50 p-1.5 text-muted-foreground hover:text-foreground hover:border-border transition-colors shrink-0">
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
              <p className="text-[11px] text-muted-foreground mt-0.5 truncate max-w-xl">
                {detail.overview || "No strategy description"}
              </p>
            </div>
          </div>
          <div className="text-right shrink-0">
            <div className={`text-2xl font-bold font-mono ${totalPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
              {totalPnl >= 0 ? "+" : ""}{totalPnl.toFixed(2)}
            </div>
            <div className="text-[10px] text-muted-foreground">
              {(perf.open_count ?? 0)} open &middot; {(perf.closed_count ?? 0)} closed
            </div>
          </div>
        </div>

        {/* Tabs */}
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
        <div className="mt-4 space-y-4">
          {/* Row 1: Performance + Capital + Settings */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1fr_minmax(200px,260px)_minmax(180px,220px)]">
            <PerformanceMetricsPanel detail={detail} />
            <CapitalPanel
              detail={detail}
              onDetailUpdate={(updates) => setDetail(prev => prev ? { ...prev, ...updates } : prev)}
            />
            <StrategySettingsPanel config={config} strategyType={detail.strategyType} botId={detail.id} />
          </div>

          {/* Row 2: Chart + Sidebar (Positions, Risk, Logic) */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
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
            <div className="space-y-4">
              <OpenPositionsPanel
                performance={detail.performance}
                onSelectSymbol={(sym) => { setActiveSymbol(sym); setSelectedTradeId(null); }}
              />
              <RiskMetricsPanel config={config} />
              <EntryLogicPanel
                conditions={(Array.isArray(config.conditions) ? config.conditions : []) as Array<Record<string, unknown>>}
                exitConditions={(Array.isArray(config.exit_conditions) ? config.exit_conditions : Array.isArray((config.ai_context as Record<string, unknown>)?.exit_conditions) ? (config.ai_context as Record<string, unknown>).exit_conditions : []) as Array<Record<string, unknown>>}
                stopLossPct={config.stop_loss_pct as number | undefined}
                takeProfitPct={config.take_profit_pct as number | undefined}
              />
            </div>
          </div>

          {/* Row 3: Universe + Market Context + Scanner */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
            <UniversePanel
              symbols={trackedSymbols}
              activeSymbol={activeSymbol}
              onSymbolSelect={(sym) => { setActiveSymbol(sym); setSelectedTradeId(null); setHoveredTradeId(null); }}
              openPositionSymbols={openPositionSymbols}
            />
            <MarketContextPanel detail={detail} />
            <MarketScannerPanel
              symbols={trackedSymbols}
              trades={detail.trades}
              conditions={(Array.isArray(config.conditions) ? config.conditions : []) as Array<Record<string, unknown>>}
            />
          </div>

          {/* Row 3.5: AI Brain — Model Settings + Leaderboard + Decision Feed */}
          {detail.aiBrainConfig ? (
            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[260px_1fr]">
              <BotModelSettings
                botId={botId}
                currentModel={
                  ((detail.aiBrainConfig as Record<string, unknown>)?.model_config as Record<string, unknown>)?.primary_model as string ?? "gpt-5.4"
                }
                autoRouteEnabled={detail.autoRouteEnabled ?? false}
                onUpdate={() => {
                  getBotDetail(botId).then(setDetail).catch(() => {});
                }}
              />
              <div className="space-y-4">
                <ModelLeaderboard
                  botId={botId}
                  onUpdate={() => getBotDetail(botId).then(setDetail).catch(() => {})}
                />
                <LiveDecisionFeed botId={botId} />
              </div>
            </div>
          ) : (
            <EnableAIBrainCTA botId={botId} onEnabled={() => getBotDetail(botId).then(setDetail).catch(() => {})} />
          )}

          {/* Row 4: Trade Log + AI Decision */}
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <TradeLogPanel
              trades={detail.trades}
              selectedTradeId={selectedTradeId}
              onSelectTrade={handleSelectTrade}
            />
            <AIReasoningPanel detail={detail} trade={selectedTrade} />
          </div>
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
