"use client";

import React from "react";
import {
  TrendingUp,
  TrendingDown,
  Target,
  Trophy,
  ArrowDownRight,
  Shield,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface MetricsRowProps {
  totalPnl: number;
  unrealizedPnl: number;
  realizedPnl: number;
  expectancy: number;
  winRate: number;
  maxDrawdown: number;
  exposure: number;
  tradesToday: number;
  tradeHistory?: number[];
  realizedPnlUnavailable?: boolean;
  winRateUnavailable?: boolean;
}

function formatCurrency(value: number, showSign = false): string {
  const formatted = Math.abs(value).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  if (showSign) {
    return value >= 0 ? `+${formatted}` : `-${formatted}`;
  }
  return value < 0 ? `-${formatted}` : formatted;
}

function Sparkline({ data }: { data: number[] }) {
  if (data.length < 2) return null;

  const width = 64;
  const height = 20;
  const padding = 1;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((value, i) => {
      const x = padding + (i / (data.length - 1)) * (width - padding * 2);
      const y = padding + (1 - (value - min) / range) * (height - padding * 2);
      return `${x},${y}`;
    })
    .join(" ");

  const lastValue = data[data.length - 1];
  const firstValue = data[0];
  const color = lastValue >= firstValue ? "rgb(52, 211, 153)" : "rgb(248, 113, 113)";

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="shrink-0"
      aria-hidden="true"
    >
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface MetricCardConfig {
  label: string;
  icon: React.ElementType;
  value: string;
  valueColor: string;
  subtitle?: string;
  subtitleColor?: string;
  sparklineData?: number[];
}

export function MetricsRow({
  totalPnl,
  unrealizedPnl,
  realizedPnl,
  expectancy,
  winRate,
  maxDrawdown,
  exposure,
  tradesToday,
  tradeHistory,
  realizedPnlUnavailable,
  winRateUnavailable,
}: MetricsRowProps) {
  const pnlPositive = totalPnl >= 0;
  const expectancyPositive = expectancy >= 0;

  const exposureColor = (() => {
    if (exposure > 0.8) return "text-red-400";
    if (exposure >= 0.5) return "text-amber-400";
    return "text-emerald-400";
  })();

  const realizedLabel = realizedPnlUnavailable ? "Realized: \u2014" : `Realized: ${formatCurrency(realizedPnl)}`;

  const cards: MetricCardConfig[] = [
    {
      label: "Total P&L",
      icon: pnlPositive ? TrendingUp : TrendingDown,
      value: formatCurrency(totalPnl, true),
      valueColor: pnlPositive ? "text-emerald-400" : "text-red-400",
      subtitle: `Unrealized: ${formatCurrency(unrealizedPnl)} \u00B7 ${realizedLabel}`,
      subtitleColor: "text-muted-foreground",
    },
    {
      label: "Expectancy",
      icon: Target,
      value: formatCurrency(expectancy, true),
      valueColor: expectancyPositive ? "text-emerald-400" : "text-red-400",
    },
    {
      label: "Win Rate",
      icon: Trophy,
      value: winRateUnavailable ? "\u2014" : `${winRate.toFixed(1)}%`,
      valueColor: winRateUnavailable ? "text-muted-foreground/50" : winRate >= 50 ? "text-emerald-400" : "text-red-400",
    },
    {
      label: "Max Drawdown",
      icon: ArrowDownRight,
      value: `-${(maxDrawdown * 100).toFixed(1)}%`,
      valueColor: "text-red-400",
    },
    {
      label: "Exposure",
      icon: Shield,
      value: `${(exposure * 100).toFixed(1)}%`,
      valueColor: exposureColor,
    },
    {
      label: "Trades / Hour",
      icon: Activity,
      value: tradesToday.toString(),
      valueColor: "text-foreground",
      sparklineData: tradeHistory,
    },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6 lg:gap-4">
      {cards.map((card) => {
        const Icon = card.icon;
        return (
          <div
            key={card.label}
            className="app-panel p-3 sm:p-4 transition-transform hover:-translate-y-0.5 min-w-0"
          >
            <div className="flex items-center gap-1.5 mb-1.5 sm:mb-2">
              <Icon className="h-3.5 w-3.5 shrink-0 text-muted-foreground/50" />
              <div className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground truncate">
                {card.label}
              </div>
            </div>

            <div className="flex items-center gap-2 min-w-0">
              <div
                className={cn(
                  "text-lg sm:text-xl lg:text-2xl font-mono font-bold tabular-nums tracking-tight truncate",
                  card.valueColor
                )}
              >
                {card.value}
              </div>
              {card.sparklineData && card.sparklineData.length >= 2 && (
                <Sparkline data={card.sparklineData} />
              )}
            </div>

            {card.subtitle && (
              <div
                className={cn(
                  "text-[10px] sm:text-xs mt-1 truncate",
                  card.subtitleColor || "text-muted-foreground"
                )}
              >
                {card.subtitle}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
