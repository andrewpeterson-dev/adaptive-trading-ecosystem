"use client";
import { BarChart3 } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import type { BotPerformanceSummary } from "@/lib/cerberus-api";
import { computeBotStats, formatPercent, formatCompactCurrency } from "@/lib/bot-visualization";
import type { BotDetail } from "@/lib/cerberus-api";

interface PerformanceMetricsPanelProps {
  detail: BotDetail;
}

function Metric({ label, value, color, show = true }: { label: string; value: string; color?: string; show?: boolean }) {
  if (!show) return null;
  return (
    <div className="rounded-xl bg-muted/20 px-3 py-2">
      <div className="text-[9px] text-muted-foreground/70 uppercase tracking-wider">{label}</div>
      <div className={`text-lg font-bold font-mono mt-0.5 ${color ?? "text-foreground"}`}>{value}</div>
    </div>
  );
}

export function PerformanceMetricsPanel({ detail }: PerformanceMetricsPanelProps) {
  const stats = computeBotStats(detail, 100000);
  const perf = detail.performance;
  const unrealized = perf.unrealized_pnl ?? 0;
  const realized = perf.realized_pnl ?? 0;
  const totalPnl = realized + unrealized;
  const openCount = perf.open_count ?? 0;
  const closedCount = perf.closed_count ?? 0;
  const hasClosed = closedCount > 0;

  return (
    <TerminalPanel title="Performance" icon={<BarChart3 className="h-3.5 w-3.5" />} accent="text-emerald-400">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="Total P&L" value={`$${totalPnl.toFixed(2)}`} color={totalPnl >= 0 ? "text-emerald-400" : "text-rose-400"} />
        <Metric label="Win Rate" value={hasClosed ? formatPercent(stats.winRatePct, 1, false) : "N/A"} color={hasClosed ? (stats.winRatePct >= 50 ? "text-emerald-400" : "text-rose-400") : "text-muted-foreground"} />
        <Metric label="Open" value={String(openCount)} />
        <Metric label="Total Trades" value={String(stats.tradeCount)} />
        <Metric label="Sharpe" value={closedCount >= 30 ? stats.sharpeRatio.toFixed(2) : "N/A"} show={true} color={closedCount >= 30 ? (stats.sharpeRatio >= 1 ? "text-emerald-400" : "text-muted-foreground") : "text-muted-foreground"} />
        <Metric label="Max Drawdown" value={hasClosed ? formatPercent(stats.maxDrawdownPct, 1, false) : "N/A"} color={hasClosed ? "text-amber-400" : "text-muted-foreground"} />
        <Metric label="Volume" value={formatCompactCurrency(perf.total_volume)} />
        <Metric label="Profit Factor" value={hasClosed && stats.profitFactor != null ? (Number.isFinite(stats.profitFactor) ? stats.profitFactor.toFixed(2) : "\u221e") : "N/A"} color={stats.profitFactor != null && stats.profitFactor >= 1 ? "text-emerald-400" : "text-muted-foreground"} />
      </div>
    </TerminalPanel>
  );
}
