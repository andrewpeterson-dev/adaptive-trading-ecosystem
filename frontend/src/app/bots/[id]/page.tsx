"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Activity, ArrowLeft, Brain, Clock3, GraduationCap, Globe, LineChart, Radar } from "lucide-react";

import { AIExplanationPanel } from "@/components/bots/AIExplanationPanel";
import { BotDetailPanel } from "@/components/bots/BotDetailPanel";
import { BotPerformanceStats } from "@/components/bots/BotPerformanceStats";
import { BotTradeChart } from "@/components/bots/BotTradeChart";
import { StrategyLogicViewer } from "@/components/bots/StrategyLogicViewer";
import { TradeHistoryTable } from "@/components/bots/TradeHistoryTable";
import { TradeTimeline } from "@/components/bots/TradeTimeline";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { PageHeader } from "@/components/layout/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { AIReasoningTab } from "@/components/bots/reasoning/AIReasoningTab";
import { LearningTab } from "@/components/bots/reasoning/LearningTab";
import { UniverseTab } from "@/components/bots/reasoning/UniverseTab";
import { cn } from "@/lib/utils";
import { getBotDetail, type BotDetail, type BotTrade } from "@/lib/cerberus-api";
import {
  buildTimelineBuckets,
  filterTradesBySymbol,
  filterTradesUntil,
  formatDateTime,
  formatTimeframe,
  getAiOverview,
  getBotConfig,
  getTrackedSymbols,
  getTradeById,
  humanizeLabel,
  summarizeRisk,
  type TimelineGranularity,
} from "@/lib/bot-visualization";

function clampIndex(index: number, length: number) {
  if (length <= 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

export default function BotDetailPage() {
  const params = useParams<{ id?: string | string[] }>();
  const botId = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "";

  const [detail, setDetail] = useState<BotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeSymbol, setActiveSymbol] = useState<string>("");
  const [selectedTradeId, setSelectedTradeId] = useState<string | null>(null);
  const [hoveredTradeId, setHoveredTradeId] = useState<string | null>(null);
  const [timelineGranularity, setTimelineGranularity] = useState<TimelineGranularity>("week");
  const [timelineIndex, setTimelineIndex] = useState(0);
  const [activeTab, setActiveTab] = useState<"overview" | "reasoning" | "learning" | "universe">("overview");

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

    if (botId) {
      void load();
    }
  }, [botId]);

  const trackedSymbols = useMemo(
    () => (detail ? getTrackedSymbols(detail) : []),
    [detail],
  );

  useEffect(() => {
    if (!detail) return;
    const fallback = detail.primarySymbol || trackedSymbols[0] || "SPY";
    setActiveSymbol((current) => (current && trackedSymbols.includes(current) ? current : fallback));
  }, [detail, trackedSymbols]);

  const symbolTrades = useMemo(
    () => (detail ? filterTradesBySymbol(detail.trades, activeSymbol || detail.primarySymbol || "SPY") : []),
    [detail, activeSymbol],
  );

  const timelineBuckets = useMemo(
    () => buildTimelineBuckets(symbolTrades, timelineGranularity),
    [symbolTrades, timelineGranularity],
  );

  useEffect(() => {
    setTimelineIndex((current) => clampIndex(current, timelineBuckets.length));
  }, [timelineBuckets.length]);

  useEffect(() => {
    setTimelineIndex(Math.max(timelineBuckets.length - 1, 0));
  }, [timelineGranularity, activeSymbol]);

  const activeBucket = timelineBuckets[timelineIndex] ?? null;
  const visibleTrades = useMemo(
    () => filterTradesUntil(symbolTrades, activeBucket?.endMs ?? null),
    [symbolTrades, activeBucket],
  );

  useEffect(() => {
    if (selectedTradeId && !visibleTrades.some((trade) => trade.id === selectedTradeId)) {
      setSelectedTradeId(null);
    }
  }, [selectedTradeId, visibleTrades]);

  useEffect(() => {
    if (hoveredTradeId && !visibleTrades.some((trade) => trade.id === hoveredTradeId)) {
      setHoveredTradeId(null);
    }
  }, [hoveredTradeId, visibleTrades]);

  const selectedTrade = useMemo(
    () => getTradeById(visibleTrades, selectedTradeId) ?? getTradeById(symbolTrades, selectedTradeId),
    [selectedTradeId, symbolTrades, visibleTrades],
  );

  const hoveredTrade = useMemo(
    () => getTradeById(visibleTrades, hoveredTradeId),
    [hoveredTradeId, visibleTrades],
  );

  const focusTrade = selectedTrade ?? hoveredTrade ?? visibleTrades[0] ?? symbolTrades[0] ?? null;

  const handleSelectTrade = (trade: BotTrade) => {
    setActiveSymbol(trade.symbol.toUpperCase());
    setSelectedTradeId(trade.id);
  };

  if (loading) {
    return (
      <div className="app-page">
        <Skeleton className="h-32 rounded-[28px]" />
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-24 rounded-[22px]" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.9fr_1.6fr]">
          <Skeleton className="h-[720px] rounded-[28px]" />
          <Skeleton className="h-[720px] rounded-[28px]" />
        </div>
      </div>
    );
  }

  if (!detail || error) {
    return (
      <div className="app-page">
        <div className="rounded-[28px] border border-rose-400/20 bg-rose-400/5 p-6 text-rose-400">
          {error || "Bot detail is unavailable."}
        </div>
      </div>
    );
  }

  const config = getBotConfig(detail);
  const riskSummary = summarizeRisk(config);
  const lastOptimizationAt = detail.learningStatus.lastOptimizationAt;

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Autonomous Bot"
        title={detail.name}
        description={getAiOverview(detail)}
        meta={
          <>
            <span className="app-pill font-mono tracking-normal">{humanizeLabel(detail.strategyType)}</span>
            <span className="app-pill font-mono tracking-normal">{detail.status}</span>
            <span className="app-pill font-mono tracking-normal">{formatTimeframe(config.timeframe)}</span>
            <span className="app-pill font-mono tracking-normal">{riskSummary} risk</span>
          </>
        }
        actions={
          <div className="flex flex-wrap gap-2">
            <Link href="/bots" className="app-button-ghost">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Bots
            </Link>
          </div>
        }
      />

      <BotPerformanceStats detail={detail} />

      {/* Tab navigation for AI Reasoning subsections */}
      <div className="flex items-center gap-1.5 rounded-[24px] border border-border/65 bg-muted/24 px-3 py-2">
        {([
          { key: "overview" as const, label: "Overview", icon: LineChart },
          { key: "reasoning" as const, label: "AI Reasoning", icon: Brain },
          { key: "learning" as const, label: "Learning", icon: GraduationCap },
          { key: "universe" as const, label: "Universe", icon: Globe },
        ]).map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setActiveTab(key)}
            className={cn(
              "flex items-center gap-1.5 rounded-full px-4 py-2.5 text-[13px] font-medium tracking-tight transition-all",
              activeTab === key
                ? "border border-primary/20 bg-primary/12 text-primary shadow-[0_14px_26px_-22px_rgba(59,130,246,0.55)]"
                : "text-muted-foreground hover:bg-muted/35 hover:text-foreground"
            )}
          >
            <Icon className="h-3.5 w-3.5" />
            {label}
          </button>
        ))}
      </div>

      {activeTab === "reasoning" && <AIReasoningTab botId={botId} />}
      {activeTab === "learning" && <LearningTab botId={botId} />}
      {activeTab === "universe" && <UniverseTab botId={botId} />}

      {activeTab === "overview" && <>
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[0.88fr_1.62fr]">
        <BotDetailPanel
          detail={detail}
          activeSymbol={activeSymbol}
          onSymbolSelect={(symbol) => {
            setActiveSymbol(symbol);
            setSelectedTradeId(null);
            setHoveredTradeId(null);
          }}
          selectedTrade={selectedTrade}
        />

        <div className="space-y-6">
          <section className="app-panel p-5 sm:p-6">
            <div className="mb-5 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
              <div>
                <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  <LineChart className="h-3.5 w-3.5 text-emerald-400" />
                  Main Chart Visualization
                </div>
                <h2 className="mt-1 text-xl font-semibold text-foreground">
                  {activeSymbol} execution map
                </h2>
                <p className="mt-2 text-sm text-muted-foreground">
                  Entries, exits, and projected risk rails are linked to the trade log and timeline.
                </p>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-2xl border border-border/60 bg-muted/15 px-4 py-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Timeline Window
                  </div>
                  <div className="mt-1 text-sm font-semibold text-foreground">
                    {activeBucket?.label ?? "Full history"}
                  </div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-muted/15 px-4 py-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                    Last Optimization
                  </div>
                  <div className="mt-1 text-sm font-semibold text-foreground">
                    {formatDateTime(lastOptimizationAt)}
                  </div>
                </div>
              </div>
            </div>

            <BotTradeChart
              symbol={activeSymbol}
              trades={visibleTrades}
              selectedTrade={selectedTrade}
              hoveredTrade={hoveredTrade}
              highlightedTradeId={selectedTradeId}
              onHoverTrade={setHoveredTradeId}
              onSelectTrade={setSelectedTradeId}
            />

            <div className="mt-5 grid gap-4 lg:grid-cols-[1.08fr_0.92fr]">
              <EquityCurveChart data={detail.equityCurve} initialCapital={100000} height={240} />
              <div className="rounded-[24px] border border-border/60 bg-muted/10 p-4">
                <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  <Activity className="h-3.5 w-3.5 text-fuchsia-400" />
                  Active Context
                </div>
                <div className="mt-4 space-y-4">
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Visible trades
                    </div>
                    <div className="mt-1 text-lg font-semibold text-foreground">{visibleTrades.length}</div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Focus trade
                    </div>
                    <div className="mt-1 text-sm text-foreground">
                      {focusTrade
                        ? `${focusTrade.symbol} ${focusTrade.side.toUpperCase()} at ${focusTrade.entryPrice != null ? `$${focusTrade.entryPrice.toFixed(2)}` : "N/A"}`
                        : "Select a marker or row"}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
                      Why it traded
                    </div>
                    <div className="mt-1 text-sm leading-6 text-muted-foreground">
                      {focusTrade?.botExplanation || focusTrade?.reasons?.[0] || "No execution rationale captured for the current focus."}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border/60 bg-background/70 px-3 py-3 text-xs text-muted-foreground">
                    Hovering markers surfaces quick trade info. Clicking a marker or log row highlights the
                    same trade on the chart.
                  </div>
                </div>
              </div>
            </div>
          </section>

          <AIExplanationPanel detail={detail} trade={focusTrade} />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[1.08fr_0.92fr]">
        <TradeTimeline
          buckets={timelineBuckets}
          granularity={timelineGranularity}
          onGranularityChange={setTimelineGranularity}
          currentIndex={timelineIndex}
          onIndexChange={(index) => setTimelineIndex(clampIndex(index, timelineBuckets.length))}
        />
        <StrategyLogicViewer detail={detail} />
      </div>

      <TradeHistoryTable
        trades={visibleTrades}
        selectedTradeId={selectedTradeId}
        onSelectTrade={handleSelectTrade}
      />

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <section className="app-panel p-5 sm:p-6">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Clock3 className="h-3.5 w-3.5 text-sky-400" />
            Version Timeline
          </div>
          <div className="mt-4 space-y-3">
            {detail.versionHistory.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-4 text-sm text-muted-foreground">
                No version history recorded for this bot yet.
              </div>
            ) : (
              detail.versionHistory.map((version) => (
                <div
                  key={version.id}
                  className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-foreground">v{version.versionNumber}</div>
                    <div className="text-xs text-muted-foreground">{formatDateTime(version.createdAt)}</div>
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {version.diffSummary || "No diff summary stored."}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>

        <section className="app-panel p-5 sm:p-6">
          <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            <Radar className="h-3.5 w-3.5 text-amber-400" />
            Optimization Runs
          </div>
          <div className="mt-4 space-y-3">
            {detail.optimizationHistory.length === 0 ? (
              <div className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-4 text-sm text-muted-foreground">
                The learning engine has not produced optimization runs for this bot yet.
              </div>
            ) : (
              detail.optimizationHistory.map((run) => (
                <div
                  key={run.id}
                  className="rounded-2xl border border-border/60 bg-muted/10 px-4 py-4"
                >
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-foreground">{humanizeLabel(run.method)}</div>
                    <div className="text-xs text-muted-foreground">{formatDateTime(run.createdAt)}</div>
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {run.summary || "No optimization summary stored."}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
      </>}
    </div>
  );
}
