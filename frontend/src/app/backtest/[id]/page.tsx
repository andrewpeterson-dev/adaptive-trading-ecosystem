"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { Play, Loader2, BarChart3, TrendingUp, List } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { StrategyRecord } from "@/types/strategy";
import type { BacktestResult, BacktestTrade } from "@/types/backtest";

function MetricCard({ label, value, format }: { label: string; value: number; format?: string }) {
  const formatted = (() => {
    if (format === "percent") return `${(value * 100).toFixed(1)}%`;
    if (format === "ratio") return value.toFixed(3);
    if (format === "currency") return `$${value.toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
    if (format === "integer") return value.toString();
    return value.toFixed(2);
  })();

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="text-xs text-muted-foreground uppercase tracking-wider">{label}</div>
      <div className="text-2xl font-mono font-bold mt-1">{formatted}</div>
    </div>
  );
}

function TradeRow({ trade }: { trade: BacktestTrade }) {
  const isWin = trade.pnl > 0;
  return (
    <tr className="border-b border-border/50 text-sm">
      <td className="py-2 pr-3">{trade.entry_date}</td>
      <td className="py-2 pr-3">{trade.exit_date}</td>
      <td className="py-2 pr-3 font-mono">${trade.entry_price.toFixed(2)}</td>
      <td className="py-2 pr-3 font-mono">${trade.exit_price.toFixed(2)}</td>
      <td className={`py-2 pr-3 font-mono font-medium ${isWin ? "text-emerald-400" : "text-red-400"}`}>
        {isWin ? "+" : ""}${trade.pnl.toFixed(2)}
      </td>
      <td className={`py-2 pr-3 font-mono text-xs ${isWin ? "text-emerald-400" : "text-red-400"}`}>
        {isWin ? "+" : ""}{trade.pnl_pct.toFixed(1)}%
      </td>
      <td className="py-2 font-mono text-muted-foreground">{trade.bars_held}d</td>
    </tr>
  );
}

export default function BacktestPage() {
  const params = useParams();
  const id = params.id as string;
  const [strategy, setStrategy] = useState<StrategyRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [activeTab, setActiveTab] = useState<"equity" | "metrics" | "trades">("equity");

  // Config
  const [symbol, setSymbol] = useState("SPY");
  const [lookbackDays, setLookbackDays] = useState(252);
  const [initialCapital, setInitialCapital] = useState(100000);

  useEffect(() => {
    async function load() {
      try {
        const data = await apiFetch<StrategyRecord>(`/api/strategies/${id}`);
        setStrategy(data);
      } catch {
        // ignore
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const runBacktest = async () => {
    setRunning(true);
    setResult(null);
    try {
      const data = await apiFetch<BacktestResult>("/api/strategies/backtest", {
        method: "POST",
        body: JSON.stringify({
          strategy_id: parseInt(id),
          symbol,
          lookback_days: lookbackDays,
          initial_capital: initialCapital,
        }),
      });
      setResult(data);
      setActiveTab("equity");
    } catch {
      // ignore
    } finally {
      setRunning(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-semibold">Backtest</h2>
        <p className="text-sm text-muted-foreground mt-0.5">
          {strategy ? strategy.name : `Strategy #${id}`}
        </p>
      </div>

      {/* Config form */}
      <div className="grid grid-cols-4 gap-3">
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Symbol
          </label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Lookback Days
          </label>
          <input
            type="number"
            value={lookbackDays}
            onChange={(e) => setLookbackDays(parseInt(e.target.value) || 252)}
            min={30}
            max={1000}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <div>
          <label className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
            Initial Capital
          </label>
          <input
            type="number"
            value={initialCapital}
            onChange={(e) => setInitialCapital(parseInt(e.target.value) || 100000)}
            min={1000}
            step={10000}
            className="mt-1 h-9 w-full rounded-md border bg-background px-3 text-sm font-mono text-right focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
        <div className="flex items-end">
          <button
            onClick={runBacktest}
            disabled={running}
            className="h-9 w-full inline-flex items-center justify-center gap-1.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-40"
          >
            {running ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Play className="h-4 w-4" />
            )}
            {running ? "Running..." : "Run Backtest"}
          </button>
        </div>
      </div>

      {/* Results */}
      {result && (
        <div className="space-y-4">
          {/* Synthetic data warning */}
          {result.synthetic_data && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-400/30 bg-amber-400/5 px-3.5 py-2.5">
              <span className="text-amber-400 text-xs font-bold uppercase tracking-widest mt-0.5">⚠ Simulated</span>
              <p className="text-xs text-amber-300/80">
                {result.data_warning ?? "This backtest used synthetic random-walk data. Results reflect logic correctness, not real market performance."}
              </p>
            </div>
          )}
          {/* Tab bar */}
          <div className="flex gap-1 border-b">
            {([
              { key: "equity" as const, label: "Equity Curve", icon: TrendingUp },
              { key: "metrics" as const, label: "Metrics", icon: BarChart3 },
              { key: "trades" as const, label: "Trades", icon: List },
            ]).map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                onClick={() => setActiveTab(key)}
                className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
                  activeTab === key
                    ? "border-primary text-foreground"
                    : "border-transparent text-muted-foreground hover:text-foreground"
                }`}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            ))}
          </div>

          {/* Equity Curve Tab */}
          {activeTab === "equity" && (
            <EquityCurveChart
              data={result.equity_curve}
              initialCapital={initialCapital}
              height={400}
            />
          )}

          {/* Metrics Tab */}
          {activeTab === "metrics" && (
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              <MetricCard label="Sharpe Ratio" value={result.metrics.sharpe_ratio} format="ratio" />
              <MetricCard label="Sortino Ratio" value={result.metrics.sortino_ratio} format="ratio" />
              <MetricCard label="Win Rate" value={result.metrics.win_rate} format="percent" />
              <MetricCard label="Max Drawdown" value={result.metrics.max_drawdown} format="percent" />
              <MetricCard label="Total Return" value={result.metrics.total_return} format="percent" />
              <MetricCard label="Total Trades" value={result.metrics.num_trades} format="integer" />
              <MetricCard label="Avg Trade P&L" value={result.metrics.avg_trade_pnl} format="currency" />
              <MetricCard label="Profit Factor" value={result.metrics.profit_factor} format="ratio" />
            </div>
          )}

          {/* Trades Tab */}
          {activeTab === "trades" && (
            <div className="rounded-lg border bg-card overflow-x-auto">
              <table className="w-full text-left">
                <thead>
                  <tr className="border-b text-xs text-muted-foreground uppercase tracking-wider">
                    <th className="py-2 px-4">Entry</th>
                    <th className="py-2 px-4">Exit</th>
                    <th className="py-2 px-4">Entry Price</th>
                    <th className="py-2 px-4">Exit Price</th>
                    <th className="py-2 px-4">P&L</th>
                    <th className="py-2 px-4">Return</th>
                    <th className="py-2 px-4">Duration</th>
                  </tr>
                </thead>
                <tbody>
                  {result.trades.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="py-8 text-center text-muted-foreground text-sm">
                        No trades executed
                      </td>
                    </tr>
                  ) : (
                    result.trades.map((t, i) => <TradeRow key={i} trade={t} />)
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}

      {!result && !running && (
        <div className="text-center py-16 border border-dashed rounded-lg">
          <BarChart3 className="h-8 w-8 text-muted-foreground/40 mx-auto mb-3" />
          <p className="text-muted-foreground">Configure parameters and run a backtest</p>
        </div>
      )}
    </div>
  );
}
