"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import {
  Activity,
  ArrowLeft,
  Bot,
  BrainCircuit,
  Gauge,
  RefreshCw,
  Sparkles,
  TrendingUp,
} from "lucide-react";

import { PageHeader } from "@/components/layout/PageHeader";
import { TradingChart } from "@/components/charts/TradingChart";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { Skeleton } from "@/components/ui/skeleton";
import { getBotDetail, type BotDetail } from "@/lib/cerberus-api";
import type { TradeMarker } from "@/types/chart";

function MetricCard({
  label,
  value,
  tone = "default",
}: {
  label: string;
  value: string;
  tone?: "default" | "positive" | "warning";
}) {
  const toneClass =
    tone === "positive"
      ? "text-emerald-400"
      : tone === "warning"
        ? "text-amber-400"
        : "text-foreground";

  return (
    <div className="rounded-2xl border border-border/60 bg-card/70 px-4 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
        {label}
      </div>
      <div className={`mt-1 text-lg font-mono font-semibold ${toneClass}`}>{value}</div>
    </div>
  );
}

function relativeTime(value: string | null | undefined) {
  if (!value) return "Not yet";
  const diffMs = Date.now() - new Date(value).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export default function BotDetailPage() {
  const params = useParams();
  const botId = params.id as string;
  const [detail, setDetail] = useState<BotDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const data = await getBotDetail(botId);
        setDetail(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load bot");
      } finally {
        setLoading(false);
      }
    }

    if (botId) {
      void load();
    }
  }, [botId]);

  const tradeMarkers = useMemo<TradeMarker[]>(
    () =>
      (detail?.trades ?? [])
        .filter((trade) => trade.createdAt && trade.entryPrice)
        .map((trade) => ({
          time: trade.entryTs ? Math.floor(new Date(trade.entryTs).getTime() / 1000) : trade.createdAt!,
          price: trade.entryPrice ?? 0,
          side: trade.side.toLowerCase().includes("sell") ? "sell" : "buy",
          tradeId: trade.id,
          label: `${trade.side.toUpperCase()} ${trade.symbol}`,
        })),
    [detail]
  );

  if (loading) {
    return (
      <div className="app-page space-y-6">
        <Skeleton className="h-28 rounded-[28px]" />
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
          {[...Array(4)].map((_, index) => <Skeleton key={index} className="h-24 rounded-2xl" />)}
        </div>
        <Skeleton className="h-80 rounded-3xl" />
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div className="app-page">
        <div className="rounded-3xl border border-red-400/20 bg-red-400/5 p-6">
          <p className="text-red-400">{error || "Bot not found"}</p>
        </div>
      </div>
    );
  }

  const primarySymbol = detail.primarySymbol || "SPY";
  const botConfig = (detail.config ?? {}) as {
    condition_groups?: unknown[];
    conditions?: unknown[];
  };
  const logicJson = JSON.stringify(
    botConfig.condition_groups?.length ? botConfig.condition_groups : botConfig.conditions,
    null,
    2,
  );
  const lastOptimizationAt = detail.learningStatus.lastOptimizationAt;
  const metrics = detail.performance;

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Autonomous Bot"
        title={detail.name}
        description={detail.overview || "AI-driven bot ready for inspection and iteration."}
        meta={
          <>
            <span className="app-pill font-mono tracking-normal">{detail.strategyType.replace(/_/g, " ")}</span>
            <span className="app-pill font-mono tracking-normal">{detail.status}</span>
            <span className="app-pill font-mono tracking-normal">Primary {primarySymbol}</span>
          </>
        }
        actions={
          <div className="flex items-center gap-2">
            <Link href="/bots" className="app-button-ghost">
              <ArrowLeft className="h-3.5 w-3.5" />
              Back to Bots
            </Link>
          </div>
        }
      />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-4">
        <MetricCard
          label="Win Rate"
          value={`${(metrics.win_rate * 100).toFixed(1)}%`}
          tone={metrics.win_rate >= 0.5 ? "positive" : "warning"}
        />
        <MetricCard
          label="Sharpe Ratio"
          value={metrics.sharpe_ratio.toFixed(2)}
          tone={metrics.sharpe_ratio >= 1 ? "positive" : "warning"}
        />
        <MetricCard
          label="Drawdown"
          value={`${(metrics.max_drawdown * 100).toFixed(1)}%`}
          tone={metrics.max_drawdown <= 0.12 ? "positive" : "warning"}
        />
        <MetricCard
          label="Net P&L"
          value={`$${metrics.total_net_pnl.toLocaleString()}`}
          tone={metrics.total_net_pnl >= 0 ? "positive" : "warning"}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-[1.4fr_0.8fr]">
        <div className="space-y-6">
          <section className="app-panel p-5 sm:p-6">
            <div className="mb-4 flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Strategy Visualization
              </h2>
            </div>
            <EquityCurveChart data={detail.equityCurve} initialCapital={100000} height={260} />
            <div className="mt-5">
              <TradingChart symbol={primarySymbol} height={360} trades={tradeMarkers} />
            </div>
          </section>

          <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <div className="app-panel p-5 sm:p-6">
              <div className="mb-3 flex items-center gap-2">
                <BrainCircuit className="h-4 w-4 text-sky-400" />
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Strategy Overview
                </h2>
              </div>
              <p className="text-sm leading-6 text-foreground">
                {detail.overview || "No overview available."}
              </p>
              {detail.sourcePrompt && (
                <div className="mt-4 rounded-2xl bg-muted/20 px-3 py-2 text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground">Source prompt:</span> {detail.sourcePrompt}
                </div>
              )}
              <div className="mt-4 flex flex-wrap gap-2">
                {detail.learningStatus.featureSignals.map((signal) => (
                  <span
                    key={signal}
                    className="rounded-full border border-border/60 px-2.5 py-1 text-[10px] font-mono text-muted-foreground"
                  >
                    {signal}
                  </span>
                ))}
              </div>
            </div>

            <div className="app-panel p-5 sm:p-6">
              <div className="mb-3 flex items-center gap-2">
                <Gauge className="h-4 w-4 text-amber-400" />
                <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Learning Status
                </h2>
              </div>
              <div className="space-y-3 text-sm">
                <div className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Last optimization</div>
                  <div className="mt-1 text-foreground">{relativeTime(lastOptimizationAt)}</div>
                </div>
                <div className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">Current summary</div>
                  <div className="mt-1 text-foreground">{detail.learningStatus.summary || "Waiting for the first optimization cycle."}</div>
                </div>
                <div className="flex flex-wrap gap-2">
                  {detail.learningStatus.methods.map((method) => (
                    <span
                      key={method}
                      className="rounded-full border border-emerald-400/20 bg-emerald-400/5 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] text-emerald-400"
                    >
                      {method.replace(/_/g, " ")}
                    </span>
                  ))}
                </div>
                <div className="space-y-2">
                  {(detail.learningStatus.parameterAdjustments ?? []).length === 0 ? (
                    <div className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3 text-xs text-muted-foreground">
                      No parameter changes have been applied yet.
                    </div>
                  ) : (
                    detail.learningStatus.parameterAdjustments.map((adjustment, index) => (
                      <div key={index} className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3 text-xs">
                        <div className="font-mono text-foreground">
                          {String(adjustment.path ?? "parameter")} {String(adjustment.old ?? "—")} → {String(adjustment.new ?? "—")}
                        </div>
                        {Boolean(adjustment.reason) && (
                          <div className="mt-1 text-muted-foreground">{String(adjustment.reason)}</div>
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </section>

          <section className="app-panel p-5 sm:p-6">
            <div className="mb-3 flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-purple-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Strategy Logic
              </h2>
            </div>
            <pre className="overflow-x-auto rounded-2xl bg-background/70 p-4 text-xs leading-6 text-foreground">
              <code>{logicJson}</code>
            </pre>
          </section>
        </div>

        <div className="space-y-6">
          <section className="app-panel p-5 sm:p-6">
            <div className="mb-3 flex items-center gap-2">
              <RefreshCw className="h-4 w-4 text-sky-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Evolution Timeline
              </h2>
            </div>
            <div className="space-y-3">
              {detail.versionHistory.map((version) => (
                <div key={version.id} className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-foreground">v{version.versionNumber}</div>
                    <div className="text-[10px] text-muted-foreground">{relativeTime(version.createdAt)}</div>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{version.diffSummary || "No diff summary recorded."}</div>
                </div>
              ))}
            </div>
          </section>

          <section className="app-panel p-5 sm:p-6">
            <div className="mb-3 flex items-center gap-2">
              <Activity className="h-4 w-4 text-emerald-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Optimization Runs
              </h2>
            </div>
            <div className="space-y-3">
              {detail.optimizationHistory.length === 0 ? (
                <div className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3 text-xs text-muted-foreground">
                  Optimization history will appear here after the learning engine completes a cycle.
                </div>
              ) : (
                detail.optimizationHistory.map((run) => (
                  <div key={run.id} className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-semibold text-foreground">{run.method.replace(/_/g, " ")}</div>
                      <div className="text-[10px] text-muted-foreground">{relativeTime(run.createdAt)}</div>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">{run.summary || "No summary available."}</div>
                  </div>
                ))
              )}
            </div>
          </section>

          <section className="app-panel p-5 sm:p-6">
            <div className="mb-3 flex items-center gap-2">
              <Bot className="h-4 w-4 text-sky-400" />
              <h2 className="text-sm font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Recent Trades
              </h2>
            </div>
            <div className="space-y-3">
              {detail.trades.slice(0, 8).map((trade) => (
                <div key={trade.id} className="rounded-2xl border border-border/60 bg-muted/20 px-3 py-3 text-xs">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-semibold text-foreground">{trade.symbol}</div>
                    <div className="font-mono text-muted-foreground">{trade.side.toUpperCase()}</div>
                  </div>
                  <div className="mt-1 text-muted-foreground">
                    {trade.netPnl != null ? `Net P&L $${trade.netPnl.toFixed(2)}` : "Trade open"}
                  </div>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
