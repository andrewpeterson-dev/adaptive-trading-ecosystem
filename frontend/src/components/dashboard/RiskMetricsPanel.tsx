"use client";

import React, { useState } from "react";
import { ShieldCheck, Info } from "lucide-react";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RiskMetricsPanelProps {
  winRate?: number; // 0-100
  profitFactor?: number;
  avgWin?: number;
  avgLoss?: number;
  maxDrawdown?: number; // 0-1
  expectancy?: number;
  sharpeRatio?: number;
  totalTrades?: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPct(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${value.toFixed(1)}%`;
}

function formatDrawdown(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return `${(value * 100).toFixed(1)}%`;
}

function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value == null) return "\u2014";
  return value.toFixed(decimals);
}

// ---------------------------------------------------------------------------
// Info tooltip (hover-based)
// ---------------------------------------------------------------------------

function InfoTooltip({ text }: { text: string }) {
  const [show, setShow] = useState(false);

  return (
    <span
      className="relative inline-flex ml-1"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Info className="h-3 w-3 text-muted-foreground/40 hover:text-muted-foreground cursor-help transition-colors" />
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 w-52 px-3 py-2 rounded-lg bg-popover border border-border shadow-lg text-xs text-foreground leading-relaxed pointer-events-none">
          {text}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px w-2 h-2 bg-popover border-r border-b border-border rotate-45" />
        </div>
      )}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Single metric cell
// ---------------------------------------------------------------------------

interface MetricCellProps {
  label: string;
  value: string;
  tooltip: string;
  colorClass?: string;
}

function MetricCell({ label, value, tooltip, colorClass }: MetricCellProps) {
  return (
    <div className="flex flex-col gap-1 px-3 py-2.5">
      <div className="flex items-center gap-0.5">
        <span className="app-metric-label">{label}</span>
        <InfoTooltip text={tooltip} />
      </div>
      <span
        className={cn(
          "text-lg font-semibold font-mono tabular-nums tracking-tight",
          colorClass || "text-foreground"
        )}
      >
        {value}
      </span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function RiskMetricsPanel({
  winRate,
  profitFactor,
  avgWin,
  avgLoss,
  maxDrawdown,
  expectancy,
  sharpeRatio,
  totalTrades,
}: RiskMetricsPanelProps) {
  const hasSufficientTrades = (totalTrades ?? 0) >= 30;

  const metrics: MetricCellProps[] = [
    {
      label: "Win Rate",
      value: formatPct(winRate),
      tooltip: "Percentage of trades that were profitable.",
      colorClass:
        winRate != null ? (winRate >= 50 ? "text-emerald-400" : "text-red-400") : undefined,
    },
    {
      label: "Profit Factor",
      value: formatNumber(profitFactor),
      tooltip: "Ratio of gross profit to gross loss. Above 1.0 means net profitable.",
      colorClass:
        profitFactor != null
          ? profitFactor > 1
            ? "text-emerald-400"
            : "text-red-400"
          : undefined,
    },
    {
      label: "Avg Win",
      value: formatCurrency(avgWin),
      tooltip: "Average profit on winning trades.",
      colorClass: "text-emerald-400",
    },
    {
      label: "Avg Loss",
      value: formatCurrency(avgLoss),
      tooltip: "Average loss on losing trades.",
      colorClass: "text-red-400",
    },
    {
      label: "Max Drawdown",
      value: formatDrawdown(maxDrawdown),
      tooltip: "Largest peak-to-trough decline in portfolio value.",
      colorClass: "text-red-400",
    },
    {
      label: "Expectancy",
      value: formatCurrency(expectancy),
      tooltip: "Average expected profit per trade based on win rate and avg win/loss.",
    },
    {
      label: "Sharpe Ratio",
      value: hasSufficientTrades ? formatNumber(sharpeRatio) : "\u2014",
      tooltip: hasSufficientTrades
        ? "Risk-adjusted return. Higher is better. Above 1.0 is considered good."
        : "Requires 30+ trades",
      colorClass: hasSufficientTrades ? undefined : "text-muted-foreground",
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-muted-foreground" />
        <h3 className="text-sm font-semibold text-foreground">Risk Metrics</h3>
        {totalTrades != null && (
          <span className="rounded-full bg-muted/50 px-2 py-1 text-[10px] font-mono text-muted-foreground">
            {totalTrades} trades
          </span>
        )}
      </div>

      <div className="app-inset p-1">
        <div className="grid grid-cols-2 gap-px">
          {metrics.map((m) => (
            <MetricCell
              key={m.label}
              label={m.label}
              value={m.value}
              tooltip={m.tooltip}
              colorClass={m.colorClass}
            />
          ))}
        </div>
      </div>
    </div>
  );
}
