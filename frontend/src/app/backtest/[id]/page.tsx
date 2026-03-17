"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Play,
  Loader2,
  BarChart3,
  TrendingUp,
  List,
  TrendingDown,
  Shuffle,
  FlaskConical,
  Grid3X3,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { StrategyRecord } from "@/types/strategy";
import type {
  BacktestResult,
  BacktestTrade,
  WalkForwardResult,
  WalkForwardSegment,
  AblationResult,
  AblationHistogramBin,
} from "@/types/backtest";
import { ParameterSweepPanel } from "@/components/backtest/ParameterSweepPanel";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

function MetricCard({
  label,
  value,
  format,
}: {
  label: string;
  value: number;
  format?: string;
}) {
  const formatted = (() => {
    if (format === "percent") return `${(value * 100).toFixed(1)}%`;
    if (format === "ratio") return value.toFixed(3);
    if (format === "currency") {
      return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    }
    if (format === "integer") return value.toString();
    return value.toFixed(2);
  })();
  const negative = formatted.startsWith("-");

  return (
    <div className="app-metric-card">
      <div className="app-metric-label">{label}</div>
      <div className={`mt-2 text-2xl font-mono font-semibold ${negative ? "text-red-300" : ""}`}>
        {formatted}
      </div>
    </div>
  );
}

function TradeRow({ trade }: { trade: BacktestTrade }) {
  const isWin = trade.pnl > 0;
  return (
    <tr>
      <td>{trade.entry_date}</td>
      <td>{trade.exit_date}</td>
      <td className="font-mono tabular-nums">${trade.entry_price.toFixed(2)}</td>
      <td className="font-mono tabular-nums">${trade.exit_price.toFixed(2)}</td>
      <td className={`font-mono tabular-nums ${isWin ? "text-emerald-300" : "text-red-300"}`}>
        {isWin ? "+" : ""}${trade.pnl.toFixed(2)}
      </td>
      <td className={`font-mono tabular-nums ${isWin ? "text-emerald-300" : "text-red-300"}`}>
        {isWin ? "+" : ""}
        {trade.pnl_pct.toFixed(1)}%
      </td>
      <td className="font-mono tabular-nums text-muted-foreground">{trade.bars_held}d</td>
    </tr>
  );
}

function DrawdownChart({
  equityCurve,
  initialCapital,
}: {
  equityCurve: { date: string; value: number }[];
  initialCapital: number;
}) {
  let peak = initialCapital;
  const ddSeries = equityCurve.map((point) => {
    if (point.value > peak) peak = point.value;
    const dd = peak > 0 ? ((point.value - peak) / peak) * 100 : 0;
    return { date: point.date, value: dd };
  });
  const minDD = Math.min(...ddSeries.map((point) => point.value));

  return (
    <div className="app-panel p-4">
      <div className="app-label mb-2">
        Drawdown
        <span className="ml-2 font-mono tracking-normal text-red-300">
          Max {minDD.toFixed(1)}%
        </span>
      </div>
      <svg
        width="100%"
        height="120"
        viewBox={`0 0 ${ddSeries.length} 120`}
        preserveAspectRatio="none"
        className="text-red-300"
      >
        <defs>
          <linearGradient id="ddGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.3" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0.05" />
          </linearGradient>
        </defs>
        <polygon
          fill="url(#ddGrad)"
          points={[
            "0,0",
            ...ddSeries.map((point, index) => {
              const y = minDD < 0 ? (point.value / minDD) * 115 : 0;
              return `${index},${y}`;
            }),
            `${ddSeries.length - 1},0`,
          ].join(" ")}
        />
        <polyline
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          points={ddSeries
            .map((point, index) => {
              const y = minDD < 0 ? (point.value / minDD) * 115 : 0;
              return `${index},${y}`;
            })
            .join(" ")}
        />
      </svg>
    </div>
  );
}

// ── Walk-Forward Results Component ───────────────────────────────────────

function WalkForwardPanel({ data }: { data: WalkForwardResult }) {
  return (
    <div className="space-y-5">
      {/* Score cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="app-metric-card">
          <div className="app-metric-label">Consistency Score</div>
          <div className={`mt-2 text-2xl font-mono font-semibold ${data.consistency_score >= 0.5 ? "text-emerald-300" : "text-red-300"}`}>
            {(data.consistency_score * 100).toFixed(0)}%
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {Math.round(data.consistency_score * data.n_segments)}/{data.n_segments} segments profitable
          </div>
        </div>
        <div className="app-metric-card">
          <div className="app-metric-label">Regime Adaptability</div>
          <div className={`mt-2 text-2xl font-mono font-semibold ${data.regime_adaptability_score <= 0 ? "text-emerald-300" : "text-amber-300"}`}>
            {data.regime_adaptability_score.toFixed(3)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {data.regime_adaptability_score <= -0.3
              ? "Strong adaptation"
              : data.regime_adaptability_score <= 0
                ? "Moderate adaptation"
                : "Weak adaptation"}
          </div>
        </div>
        <MetricCard label="Mean Sharpe" value={data.aggregate_metrics.mean_sharpe} format="ratio" />
        <MetricCard label="Mean Return" value={data.aggregate_metrics.mean_return} format="percent" />
      </div>

      {/* Segment table */}
      <div className="app-table-shell overflow-x-auto">
        <table className="app-table">
          <thead>
            <tr>
              <th>Segment</th>
              <th>Start</th>
              <th>End</th>
              <th>Sharpe</th>
              <th>Return</th>
              <th>Max DD</th>
              <th>Win Rate</th>
              <th>Trades</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {data.segments.map((seg: WalkForwardSegment, i: number) => {
              const profitable = seg.metrics.total_return > 0;
              return (
                <tr key={i}>
                  <td className="font-mono text-muted-foreground">#{i + 1}</td>
                  <td>{seg.start}</td>
                  <td>{seg.end}</td>
                  <td className="font-mono tabular-nums">{seg.metrics.sharpe.toFixed(3)}</td>
                  <td className={`font-mono tabular-nums ${profitable ? "text-emerald-300" : "text-red-300"}`}>
                    {(seg.metrics.total_return * 100).toFixed(1)}%
                  </td>
                  <td className="font-mono tabular-nums text-red-300">
                    {(seg.metrics.max_drawdown * 100).toFixed(1)}%
                  </td>
                  <td className="font-mono tabular-nums">
                    {(seg.metrics.win_rate * 100).toFixed(0)}%
                  </td>
                  <td className="font-mono tabular-nums">{seg.metrics.num_trades}</td>
                  <td>
                    <span className={`inline-block h-2 w-2 rounded-full ${profitable ? "bg-emerald-400" : "bg-red-400"}`} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Segment performance bar chart */}
      <div className="app-panel p-4">
        <div className="app-label mb-3">Per-Segment Returns</div>
        <div className="flex items-end gap-1" style={{ height: 120 }}>
          {data.segments.map((seg: WalkForwardSegment, i: number) => {
            const maxAbs = Math.max(
              ...data.segments.map((s) => Math.abs(s.metrics.total_return)),
              0.01
            );
            const pct = seg.metrics.total_return / maxAbs;
            const height = Math.abs(pct) * 100;
            const isUp = seg.metrics.total_return >= 0;
            return (
              <div
                key={i}
                className="flex-1 flex flex-col items-center justify-end"
                style={{ height: "100%" }}
              >
                {isUp ? (
                  <div
                    className="w-full rounded-t bg-emerald-400/70"
                    style={{ height: `${height}%`, minHeight: 2 }}
                    title={`#${i + 1}: ${(seg.metrics.total_return * 100).toFixed(1)}%`}
                  />
                ) : (
                  <div className="flex-1" />
                )}
                {!isUp && (
                  <div
                    className="w-full rounded-b bg-red-400/70"
                    style={{ height: `${height}%`, minHeight: 2 }}
                    title={`#${i + 1}: ${(seg.metrics.total_return * 100).toFixed(1)}%`}
                  />
                )}
                <div className="mt-1 text-[10px] text-muted-foreground font-mono">
                  {i + 1}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Ablation Study Results Component ─────────────────────────────────────

function AblationPanel({ data }: { data: AblationResult }) {
  const maxCount = Math.max(...data.random_distribution_histogram.map((b) => b.count), 1);

  return (
    <div className="space-y-5">
      {/* Score cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <div className="app-metric-card">
          <div className="app-metric-label">P-Value</div>
          <div className={`mt-2 text-2xl font-mono font-semibold ${data.is_significant ? "text-emerald-300" : "text-amber-300"}`}>
            {data.p_value.toFixed(4)}
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            {data.is_significant ? "Statistically significant (p < 0.05)" : "Not significant (p >= 0.05)"}
          </div>
        </div>
        <div className="app-metric-card">
          <div className="app-metric-label">Percentile</div>
          <div className={`mt-2 text-2xl font-mono font-semibold ${data.percentile >= 95 ? "text-emerald-300" : data.percentile >= 75 ? "text-blue-300" : "text-muted-foreground"}`}>
            {data.percentile.toFixed(1)}%
          </div>
          <div className="mt-1 text-xs text-muted-foreground">
            Beats {data.percentile.toFixed(0)}% of random strategies
          </div>
        </div>
        <MetricCard label="Strategy Sharpe" value={data.strategy_sharpe} format="ratio" />
        <MetricCard label="Random Mean Sharpe" value={data.random_mean_sharpe} format="ratio" />
      </div>

      {/* Significance badge */}
      <div className="app-panel p-4 flex items-center gap-3">
        <div className={`h-3 w-3 rounded-full ${data.is_significant ? "bg-emerald-400" : "bg-amber-400"}`} />
        <div className="text-sm">
          {data.is_significant ? (
            <span>
              Your strategy&apos;s Sharpe of <strong className="font-mono">{data.strategy_sharpe.toFixed(3)}</strong> is
              in the <strong className="font-mono text-emerald-300">{data.percentile.toFixed(1)}th</strong> percentile
              of {data.n_random_trials.toLocaleString()} random strategies. This is statistically significant
              &mdash; unlikely due to chance alone.
            </span>
          ) : (
            <span>
              Your strategy&apos;s Sharpe of <strong className="font-mono">{data.strategy_sharpe.toFixed(3)}</strong> is
              in the <strong className="font-mono text-amber-300">{data.percentile.toFixed(1)}th</strong> percentile
              of {data.n_random_trials.toLocaleString()} random strategies. This is <em>not</em> statistically
              significant &mdash; the performance could be due to chance.
            </span>
          )}
        </div>
      </div>

      {/* Histogram */}
      <div className="app-panel p-4">
        <div className="app-label mb-3">
          Random Sharpe Distribution
          <span className="ml-2 font-mono tracking-normal text-muted-foreground">
            n={data.n_random_trials.toLocaleString()}
          </span>
        </div>
        <div className="relative" style={{ height: 160 }}>
          <div className="flex items-end gap-px h-full">
            {data.random_distribution_histogram.map((bin: AblationHistogramBin, i: number) => {
              const barHeight = maxCount > 0 ? (bin.count / maxCount) * 100 : 0;
              const isStrategy = bin.contains_strategy;
              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col justify-end"
                  style={{ height: "100%" }}
                >
                  <div
                    className={`w-full rounded-t ${isStrategy ? "bg-blue-400" : "bg-zinc-600/60"}`}
                    style={{ height: `${barHeight}%`, minHeight: bin.count > 0 ? 2 : 0 }}
                    title={`${bin.bin_start.toFixed(2)} to ${bin.bin_end.toFixed(2)}: ${bin.count} strategies${isStrategy ? " (YOUR STRATEGY)" : ""}`}
                  />
                </div>
              );
            })}
          </div>
          {/* Strategy marker line */}
          {(() => {
            const bins = data.random_distribution_histogram;
            if (bins.length === 0) return null;
            const totalRange = bins[bins.length - 1].bin_end - bins[0].bin_start;
            if (totalRange <= 0) return null;
            const leftPct = ((data.strategy_sharpe - bins[0].bin_start) / totalRange) * 100;
            const clampedLeft = Math.max(0, Math.min(100, leftPct));
            return (
              <div
                className="absolute top-0 bottom-0 w-0.5 bg-blue-400"
                style={{ left: `${clampedLeft}%` }}
              >
                <div className="absolute -top-1 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-blue-400 px-1.5 py-0.5 text-[10px] font-mono font-bold text-black">
                  {data.strategy_sharpe.toFixed(3)}
                </div>
              </div>
            );
          })()}
        </div>
        <div className="mt-2 flex justify-between text-[10px] text-muted-foreground font-mono">
          <span>{data.random_distribution_histogram[0]?.bin_start.toFixed(2)}</span>
          <span>{data.random_distribution_histogram[data.random_distribution_histogram.length - 1]?.bin_end.toFixed(2)}</span>
        </div>
      </div>
    </div>
  );
}

// ── Main Page Component ──────────────────────────────────────────────────

type TabKey = "equity" | "drawdown" | "metrics" | "trades" | "walk-forward" | "ablation";

export default function BacktestPage() {
  const params = useParams<{ id?: string | string[] }>();
  const id = Array.isArray(params?.id) ? params.id[0] : params?.id ?? "";
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("equity");
  const [symbol, setSymbol] = useState("SPY");
  const [lookbackDays, setLookbackDays] = useState(252);
  const [initialCapital, setInitialCapital] = useState(100000);

  // Walk-forward state
  const [wfRunning, setWfRunning] = useState(false);
  const [wfError, setWfError] = useState<string | null>(null);
  const [wfResult, setWfResult] = useState<WalkForwardResult | null>(null);

  // Ablation state
  const [abRunning, setAbRunning] = useState(false);
  const [abError, setAbError] = useState<string | null>(null);
  const [abResult, setAbResult] = useState<AblationResult | null>(null);

  // Parameter sweep state
  const [showSweep, setShowSweep] = useState(false);

  useEffect(() => {
    async function load() {
      if (!id) {
        setLoadError("Missing strategy ID");
        setLoading(false);
        return;
      }
      try {
        const data = await apiFetch<StrategyRecord>(`/api/strategies/${id}`);
        setStrategy(data);
        if (data.symbols?.length) setSymbol(data.symbols[0]);
      } catch (err) {
        setLoadError(err instanceof Error ? err.message : "Failed to load strategy");
      } finally {
        setLoading(false);
      }
    }

    load();
  }, [id]);

  const runBacktest = async () => {
    if (!id) {
      setRunError("Missing strategy ID");
      return;
    }
    setRunning(true);
    setResult(null);
    setRunError(null);
    try {
      const data = await apiFetch<BacktestResult>("/api/strategies/backtest", {
        method: "POST",
        timeoutMs: 120_000,
        body: JSON.stringify({
          strategy_id: parseInt(id, 10),
          symbol,
          lookback_days: lookbackDays,
          initial_capital: initialCapital,
        }),
      });
      setResult(data);
      setActiveTab("equity");
    } catch (err) {
      setRunError(err instanceof Error ? err.message : "Backtest failed");
    } finally {
      setRunning(false);
    }
  };

  const runWalkForward = async () => {
    if (!id) return;
    setWfRunning(true);
    setWfError(null);
    setWfResult(null);
    try {
      const data = await apiFetch<WalkForwardResult>("/api/strategies/walk-forward", {
        method: "POST",
        timeoutMs: 300_000,
        body: JSON.stringify({
          strategy_id: parseInt(id, 10),
          symbol,
          lookback_days: Math.max(lookbackDays, 504), // walk-forward needs more history
          n_segments: 6,
          initial_capital: initialCapital,
        }),
      });
      setWfResult(data);
      setActiveTab("walk-forward");
    } catch (err) {
      setWfError(err instanceof Error ? err.message : "Walk-forward failed");
    } finally {
      setWfRunning(false);
    }
  };

  const runAblation = async () => {
    if (!id) return;
    setAbRunning(true);
    setAbError(null);
    setAbResult(null);
    try {
      const data = await apiFetch<AblationResult>("/api/strategies/ablation-study", {
        method: "POST",
        timeoutMs: 300_000,
        body: JSON.stringify({
          strategy_id: parseInt(id, 10),
          symbol,
          lookback_days: lookbackDays,
          n_random_trials: 1000,
          initial_capital: initialCapital,
        }),
      });
      setAbResult(data);
      setActiveTab("ablation");
    } catch (err) {
      setAbError(err instanceof Error ? err.message : "Ablation study failed");
    } finally {
      setAbRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="app-panel">
        <EmptyState title="Failed to load strategy" description={loadError} />
      </div>
    );
  }

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Research"
        title="Backtest"
        description="Run a fast historical validation loop against a selected symbol, capital base, and lookback window."
        meta={
          <>
            <Badge variant="neutral" className="tracking-normal">
              {strategy ? strategy.name : `Strategy #${id}`}
            </Badge>
            {result && (
              <Badge variant="info" className="tracking-normal font-mono">
                {(result.symbol ?? symbol).toUpperCase()} • {(result.timeframe ?? strategy?.timeframe ?? "1D")} • Commission{" "}
                {((result.commission_pct ?? 0) * 100).toFixed(3)}% • Slippage{" "}
                {((result.slippage_pct ?? 0) * 100).toFixed(3)}%
              </Badge>
            )}
          </>
        }
      />

      <div className="app-panel p-5 sm:p-6">
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div className="space-y-2">
            <label className="app-label">Symbol</label>
            <Input
              value={symbol}
              onChange={(event) => setSymbol(event.target.value.toUpperCase())}
              className="font-mono"
            />
          </div>
          <div className="space-y-2">
            <label className="app-label">Lookback Days</label>
            <Input
              type="number"
              value={lookbackDays}
              min={30}
              max={1000}
              onChange={(event) => setLookbackDays(parseInt(event.target.value, 10) || 252)}
              className="font-mono text-right"
            />
          </div>
          <div className="space-y-2">
            <label className="app-label">Initial Capital</label>
            <Input
              type="number"
              value={initialCapital}
              min={1000}
              step={10000}
              onChange={(event) =>
                setInitialCapital(parseInt(event.target.value, 10) || 100000)
              }
              className="font-mono text-right"
            />
          </div>
          <div className="flex items-end gap-2">
            <Button onClick={runBacktest} disabled={running} variant="primary" className="flex-1">
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {running ? "Running..." : "Backtest"}
            </Button>
          </div>
        </div>

        {/* Advanced analysis buttons */}
        <div className="mt-4 flex flex-wrap gap-2 border-t border-border/50 pt-4">
          <Button
            onClick={runWalkForward}
            disabled={wfRunning}
            variant="secondary"
            size="sm"
          >
            {wfRunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Shuffle className="h-3.5 w-3.5" />
            )}
            {wfRunning ? "Running Walk-Forward..." : "Walk-Forward Validation"}
          </Button>
          <Button
            onClick={runAblation}
            disabled={abRunning}
            variant="secondary"
            size="sm"
          >
            {abRunning ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <FlaskConical className="h-3.5 w-3.5" />
            )}
            {abRunning ? "Running Ablation..." : "Ablation Study"}
          </Button>
          <Button
            onClick={() => setShowSweep(true)}
            variant="secondary"
            size="sm"
          >
            <Grid3X3 className="h-3.5 w-3.5" />
            Parameter Sweep
          </Button>
        </div>
      </div>

      {/* Error messages */}
      {runError && (
        <div className="app-inset border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
          {runError}
        </div>
      )}
      {wfError && (
        <div className="app-inset border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
          Walk-Forward: {wfError}
        </div>
      )}
      {abError && (
        <div className="app-inset border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
          Ablation: {abError}
        </div>
      )}

      {/* Tabs + content */}
      {(result || wfResult || abResult) && (
        <div className="space-y-5">
          <div className="app-inset flex flex-wrap items-center gap-2 p-2">
            {result && ([
              { key: "equity" as TabKey, label: "Equity Curve", icon: TrendingUp },
              { key: "drawdown" as TabKey, label: "Drawdown", icon: TrendingDown },
              { key: "metrics" as TabKey, label: "Metrics", icon: BarChart3 },
              { key: "trades" as TabKey, label: "Trades", icon: List },
            ]).map(({ key, label, icon: Icon }) => (
              <Button
                key={key}
                onClick={() => setActiveTab(key)}
                variant={activeTab === key ? "secondary" : "ghost"}
                size="sm"
                className="rounded-full px-4"
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </Button>
            ))}
            {wfResult && (
              <Button
                onClick={() => setActiveTab("walk-forward")}
                variant={activeTab === "walk-forward" ? "secondary" : "ghost"}
                size="sm"
                className="rounded-full px-4"
              >
                <Shuffle className="h-3.5 w-3.5" />
                Walk-Forward
              </Button>
            )}
            {abResult && (
              <Button
                onClick={() => setActiveTab("ablation")}
                variant={activeTab === "ablation" ? "secondary" : "ghost"}
                size="sm"
                className="rounded-full px-4"
              >
                <FlaskConical className="h-3.5 w-3.5" />
                Ablation
              </Button>
            )}
          </div>

          {activeTab === "equity" && result && (
            <div className="app-panel p-4 sm:p-5">
              <EquityCurveChart data={result.equity_curve} height={360} />
            </div>
          )}

          {activeTab === "drawdown" && result && (
            <DrawdownChart
              equityCurve={result.equity_curve}
              initialCapital={initialCapital}
            />
          )}

          {activeTab === "metrics" && result && (
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <MetricCard label="Total Return" value={result.metrics.total_return} format="percent" />
              <MetricCard label="Sharpe" value={result.metrics.sharpe_ratio} format="ratio" />
              <MetricCard label="Max Drawdown" value={result.metrics.max_drawdown} format="percent" />
              <MetricCard label="Win Rate" value={result.metrics.win_rate} format="percent" />
              <MetricCard label="Profit Factor" value={result.metrics.profit_factor} format="ratio" />
              <MetricCard label="Trades" value={result.metrics.num_trades} format="integer" />
              <MetricCard
                label="Ending Equity"
                value={result.equity_curve[result.equity_curve.length - 1]?.value ?? initialCapital}
                format="currency"
              />
              <MetricCard
                label="Net P&L"
                value={(result.equity_curve[result.equity_curve.length - 1]?.value ?? initialCapital) - initialCapital}
                format="currency"
              />
            </div>
          )}

          {activeTab === "trades" && result && (
            <div className="app-table-shell overflow-x-auto">
              {result.trades.length === 0 ? (
                <EmptyState
                  title="No trades generated"
                  description="This backtest did not produce any fills for the selected symbol and window."
                  className="py-12"
                />
              ) : (
                <table className="app-table">
                  <thead>
                    <tr>
                      <th>Entry Date</th>
                      <th>Exit Date</th>
                      <th>Entry</th>
                      <th>Exit</th>
                      <th>P&L</th>
                      <th>P&L %</th>
                      <th>Bars Held</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.trades.map((trade, index) => (
                      <TradeRow key={index} trade={trade} />
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {activeTab === "walk-forward" && wfResult && (
            <WalkForwardPanel data={wfResult} />
          )}

          {activeTab === "ablation" && abResult && (
            <AblationPanel data={abResult} />
          )}
        </div>
      )}

      {showSweep && strategy && (
        <ParameterSweepPanel
          strategyId={strategy.id}
          strategyName={strategy.name}
          symbol={symbol}
          timeframe="1D"
          conditions={strategy.conditions || strategy.condition_groups?.[0]?.conditions || []}
        />
      )}
    </div>
  );
}
