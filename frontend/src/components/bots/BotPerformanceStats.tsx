"use client";

import type { BotDetail } from "@/lib/cerberus-api";
import {
  computeBotStats,
  formatCompactCurrency,
  formatPercent,
} from "@/lib/bot-visualization";

interface BotPerformanceStatsProps {
  detail: BotDetail;
  initialCapital?: number;
}

function metricTone(value: number, direction: "up" | "down" = "up") {
  if (direction === "up") {
    return value >= 0 ? "text-emerald-400" : "text-rose-400";
  }
  return value <= 0 ? "text-emerald-400" : "text-amber-400";
}

function StatCard({
  label,
  value,
  hint,
  className,
}: {
  label: string;
  value: string;
  hint?: string;
  className?: string;
}) {
  return (
    <div className="rounded-[22px] border border-border/60 bg-card/75 px-4 py-4 shadow-[0_18px_48px_-38px_rgba(15,23,42,0.45)]">
      <div className="text-[10px] font-semibold uppercase tracking-[0.2em] text-muted-foreground">
        {label}
      </div>
      <div className={`mt-2 text-xl font-semibold tracking-tight ${className ?? "text-foreground"}`}>
        {value}
      </div>
      {hint && <div className="mt-2 text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

export function BotPerformanceStats({
  detail,
  initialCapital = 100000,
}: BotPerformanceStatsProps) {
  const stats = computeBotStats(detail, initialCapital);
  const profitFactor =
    stats.profitFactor == null
      ? "N/A"
      : Number.isFinite(stats.profitFactor)
        ? stats.profitFactor.toFixed(2)
        : "∞";

  return (
    <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <StatCard
        label="Total Return"
        value={formatPercent(stats.totalReturnPct, 1, false)}
        hint={`Net P&L ${formatCompactCurrency(stats.totalNetPnl)}`}
        className={metricTone(stats.totalReturnPct)}
      />
      <StatCard
        label="Win Rate"
        value={formatPercent(stats.winRatePct, 1, false)}
        hint={`${stats.tradeCount} closed trades tracked`}
        className={metricTone(stats.winRatePct - 50)}
      />
      <StatCard
        label="Sharpe Ratio"
        value={stats.sharpeRatio.toFixed(2)}
        hint="Risk-adjusted return"
        className={metricTone(stats.sharpeRatio - 1)}
      />
      <StatCard
        label="Average Trade"
        value={formatPercent(stats.averageTradeReturnPct, 2, false)}
        hint="Mean return per trade"
        className={metricTone(stats.averageTradeReturnPct)}
      />
      <StatCard
        label="Max Drawdown"
        value={formatPercent(stats.maxDrawdownPct, 1, false)}
        hint="Peak-to-trough decline"
        className={metricTone(stats.maxDrawdownPct, "down")}
      />
      <StatCard
        label="Number of Trades"
        value={String(stats.tradeCount)}
        hint="Executions recorded for this bot"
      />
      <StatCard
        label="Profit Factor"
        value={profitFactor}
        hint="Gross profits divided by gross losses"
        className={stats.profitFactor != null && stats.profitFactor >= 1 ? "text-emerald-400" : "text-amber-400"}
      />
      <StatCard
        label="Volume Traded"
        value={formatCompactCurrency(detail.performance.total_volume)}
        hint="Entry notional across all trades"
      />
    </section>
  );
}
