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
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { StrategyRecord } from "@/types/strategy";
import type { BacktestResult, BacktestTrade } from "@/types/backtest";
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

export default function BacktestPage() {
  const params = useParams();
  const id = params.id as string;
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [activeTab, setActiveTab] = useState<"equity" | "drawdown" | "metrics" | "trades">(
    "equity"
  );
  const [symbol, setSymbol] = useState("SPY");
  const [lookbackDays, setLookbackDays] = useState(252);
  const [initialCapital, setInitialCapital] = useState(100000);

  useEffect(() => {
    async function load() {
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
    setRunning(true);
    setResult(null);
    setRunError(null);
    try {
      const data = await apiFetch<BacktestResult>("/api/strategies/backtest", {
        method: "POST",
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
          <div className="flex items-end">
            <Button onClick={runBacktest} disabled={running} variant="primary" className="w-full">
              {running ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Play className="h-4 w-4" />
              )}
              {running ? "Running..." : "Run Backtest"}
            </Button>
          </div>
        </div>
      </div>

      {runError && (
        <div className="app-inset border-red-400/20 bg-red-400/5 px-4 py-3 text-sm text-red-300">
          {runError}
        </div>
      )}

      {result && (
        <div className="space-y-5">
          <div className="app-inset flex flex-wrap items-center gap-2 p-2">
            {([
              { key: "equity" as const, label: "Equity Curve", icon: TrendingUp },
              { key: "drawdown" as const, label: "Drawdown", icon: TrendingDown },
              { key: "metrics" as const, label: "Metrics", icon: BarChart3 },
              { key: "trades" as const, label: "Trades", icon: List },
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
          </div>

          {activeTab === "equity" && (
            <div className="app-panel p-4 sm:p-5">
              <EquityCurveChart data={result.equity_curve} height={360} />
            </div>
          )}

          {activeTab === "drawdown" && (
            <DrawdownChart
              equityCurve={result.equity_curve}
              initialCapital={initialCapital}
            />
          )}

          {activeTab === "metrics" && (
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

          {activeTab === "trades" && (
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
        </div>
      )}
    </div>
  );
}
