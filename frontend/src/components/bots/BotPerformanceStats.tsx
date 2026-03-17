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
  const perf = detail.performance;
  const unrealizedPnl = perf.unrealized_pnl ?? 0;
  const realizedPnl = perf.realized_pnl ?? 0;
  const openCount = perf.open_count ?? 0;
  const closedCount = perf.closed_count ?? 0;
  const openPositions = perf.open_positions ?? [];
  const totalPnl = realizedPnl + unrealizedPnl;
  const profitFactor =
    stats.profitFactor == null
      ? "N/A"
      : Number.isFinite(stats.profitFactor)
        ? stats.profitFactor.toFixed(2)
        : "\u221e";

  return (
    <div className="space-y-4">
      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          label="Total P&L"
          value={`$${totalPnl.toFixed(2)}`}
          hint={realizedPnl !== 0 ? `Realized $${realizedPnl.toFixed(2)} + Unrealized $${unrealizedPnl.toFixed(2)}` : `Unrealized $${unrealizedPnl.toFixed(2)}`}
          className={metricTone(totalPnl)}
        />
        <StatCard
          label="Win Rate"
          value={closedCount > 0 ? formatPercent(stats.winRatePct, 1, false) : "N/A"}
          hint={closedCount > 0 ? `${closedCount} closed trades` : `${openCount} open, 0 closed`}
          className={closedCount > 0 ? metricTone(stats.winRatePct - 50) : "text-muted-foreground"}
        />
        <StatCard
          label="Open Positions"
          value={String(openCount)}
          hint={openPositions.length > 0
            ? openPositions.map(p => `${p.symbol} $${(p.unrealizedPnl as number)?.toFixed(2)}`).join(" | ")
            : "No open positions"}
          className={unrealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}
        />
        <StatCard
          label="Total Trades"
          value={`${stats.tradeCount}`}
          hint={`${openCount} open, ${closedCount} closed`}
        />
        <StatCard
          label="Sharpe Ratio"
          value={closedCount >= 5 ? stats.sharpeRatio.toFixed(2) : "N/A"}
          hint="Risk-adjusted return"
          className={closedCount >= 5 ? metricTone(stats.sharpeRatio - 1) : "text-muted-foreground"}
        />
        <StatCard
          label="Max Drawdown"
          value={closedCount > 0 ? formatPercent(stats.maxDrawdownPct, 1, false) : "N/A"}
          hint="Peak-to-trough decline"
          className={closedCount > 0 ? metricTone(stats.maxDrawdownPct, "down") : "text-muted-foreground"}
        />
        <StatCard
          label="Profit Factor"
          value={closedCount > 0 ? profitFactor : "N/A"}
          hint="Gross profits divided by gross losses"
          className={stats.profitFactor != null && stats.profitFactor >= 1 ? "text-emerald-400" : "text-muted-foreground"}
        />
        <StatCard
          label="Volume Traded"
          value={formatCompactCurrency(detail.performance.total_volume)}
          hint="Entry notional across all trades"
        />
      </section>
    </div>
  );
}
