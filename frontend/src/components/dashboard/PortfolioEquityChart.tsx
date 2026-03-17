"use client";

import React, { useState, useEffect, useCallback, useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
} from "recharts";
import { Loader2, AlertTriangle, TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useThemeMode } from "@/hooks/useThemeMode";
import { useTradingMode } from "@/hooks/useTradingMode";
import { apiFetch } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type Period = "1D" | "1W" | "1M" | "3M" | "1Y";

interface EquityPoint {
  date: string;
  equity: number;
}

interface EquityHistoryResponse {
  points: EquityPoint[];
  initial_capital: number;
}

interface PortfolioEquityChartProps {
  height?: number;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PERIODS: Period[] = ["1D", "1W", "1M", "3M", "1Y"];

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatDollar(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatDateLabel(dateStr: string, period: Period): string {
  const d = new Date(dateStr);
  if (period === "1D") {
    return d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  }
  if (period === "1W" || period === "1M") {
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }
  return d.toLocaleDateString("en-US", { month: "short", year: "2-digit" });
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

interface TooltipPayloadEntry {
  value: number;
  payload: EquityPoint;
}

function ChartTooltip({
  active,
  payload,
  isDark,
  initialCapital,
}: {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  isDark: boolean;
  initialCapital: number;
}) {
  if (!active || !payload || payload.length === 0) return null;

  const point = payload[0];
  const equity = point.value;
  const change = equity - initialCapital;
  const changePct = initialCapital > 0 ? (change / initialCapital) * 100 : 0;
  const isPositive = change >= 0;
  const dateStr = point.payload.date;
  const d = new Date(dateStr);
  const formatted = d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-xs shadow-lg",
        isDark
          ? "border-white/10 bg-[#0f1729]"
          : "border-gray-200 bg-white",
      )}
    >
      <p className="mb-1 font-medium text-muted-foreground">{formatted}</p>
      <p className="font-mono font-semibold text-foreground">
        {formatDollar(equity)}
      </p>
      <p
        className={cn(
          "font-mono text-[10px] font-bold",
          isPositive ? "text-emerald-500" : "text-red-500",
        )}
      >
        {isPositive ? "+" : ""}
        {formatDollar(change)} ({isPositive ? "+" : ""}
        {changePct.toFixed(2)}%)
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PortfolioEquityChart({ height = 340 }: PortfolioEquityChartProps) {
  const { isDark } = useThemeMode();
  const { mode } = useTradingMode();

  const [period, setPeriod] = useState<Period>("1M");
  const [data, setData] = useState<EquityPoint[]>([]);
  const [initialCapital, setInitialCapital] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const gridColor = isDark ? "#1e293b" : "#e2e8f0";
  const textColor = isDark ? "#94a3b8" : "#475569";

  const fetchEquity = useCallback(
    async (p: Period) => {
      setLoading(true);
      setError(null);
      try {
        const res = await apiFetch<EquityHistoryResponse>(
          `/api/trading/equity-history?period=${p}&mode=${mode}`,
        );
        setData(res.points || []);
        setInitialCapital(res.initial_capital || 0);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load equity data");
      } finally {
        setLoading(false);
      }
    },
    [mode],
  );

  useEffect(() => {
    fetchEquity(period);
  }, [period, fetchEquity]);

  // Derived values
  const isPositive = useMemo(() => {
    if (data.length < 2) return true;
    const first = data[0].equity;
    const last = data[data.length - 1].equity;
    return last >= first;
  }, [data]);

  const currentEquity = data.length > 0 ? data[data.length - 1].equity : 0;
  const startEquity = data.length > 0 ? data[0].equity : 0;
  const totalChange = currentEquity - startEquity;
  const totalChangePct =
    startEquity > 0 ? (totalChange / startEquity) * 100 : 0;

  const strokeColor = isPositive ? "#10b981" : "#ef4444";
  const gradientId = "portfolioEquityGradient";

  const yDomain = useMemo(() => {
    if (data.length === 0) return [0, 100];
    const values = data.map((d) => d.equity);
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.08 || max * 0.02 || 100;
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [data]);

  return (
    <div className="flex h-full flex-col gap-2">
      {/* Header row: equity value + period selector */}
      <div className="flex items-center justify-between px-3 pt-1">
        <div className="flex items-center gap-3">
          <span className="text-xs font-mono font-semibold text-muted-foreground">
            Portfolio Equity
          </span>
          {data.length > 0 && !loading && (
            <div className="flex items-center gap-2">
              <span className="text-sm font-mono font-bold text-foreground">
                {formatDollar(currentEquity)}
              </span>
              <span
                className={cn(
                  "rounded-full px-1.5 py-0.5 text-[10px] font-mono font-bold",
                  isPositive
                    ? "bg-emerald-500/10 text-emerald-500"
                    : "bg-red-500/10 text-red-500",
                )}
              >
                {totalChange >= 0 ? "+" : ""}
                {totalChangePct.toFixed(2)}%
              </span>
            </div>
          )}
        </div>
        <div className="flex items-center gap-1">
          {PERIODS.map((p) => (
            <button
              key={p}
              type="button"
              onClick={() => setPeriod(p)}
              className={cn(
                "rounded-full px-2.5 py-1 text-[10px] font-mono font-semibold transition-colors",
                period === p
                  ? "bg-foreground text-background"
                  : "bg-black/[0.03] text-muted-foreground hover:text-foreground dark:bg-white/[0.03]",
              )}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="relative flex-1 overflow-hidden rounded-md" style={{ minHeight: height }}>
        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-background/80 backdrop-blur-sm">
            <AlertTriangle className="h-5 w-5 text-muted-foreground/60" />
            <span className="text-sm font-semibold text-foreground">
              Equity data unavailable
            </span>
            <span className="max-w-sm text-center text-xs text-muted-foreground">
              {error}
            </span>
            <button
              type="button"
              onClick={() => void fetchEquity(period)}
              className="mt-1 rounded-md bg-foreground/10 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-foreground/20"
            >
              Retry
            </button>
          </div>
        )}

        {!loading && !error && (data.length === 0 || (data.length <= 2 && totalChange === 0)) && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-primary/10 flex items-center justify-center">
              <TrendingUp className="h-6 w-6 text-primary/50" />
            </div>
            <div className="text-center">
              <p className="text-sm font-medium text-foreground">No trading activity yet</p>
              <p className="text-xs text-muted-foreground mt-1 max-w-xs">
                Your portfolio equity chart will come alive once bots start trading or you execute your first trade.
              </p>
            </div>
            {initialCapital > 0 && (
              <p className="text-xs text-muted-foreground/60 font-mono">
                Starting capital: ${initialCapital.toLocaleString()}
              </p>
            )}
          </div>
        )}

        {data.length > 0 && (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
              <defs>
                <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={strokeColor} stopOpacity={0.25} />
                  <stop offset="95%" stopColor={strokeColor} stopOpacity={0} />
                </linearGradient>
              </defs>

              <CartesianGrid
                strokeDasharray="3 3"
                stroke={gridColor}
                vertical={false}
              />

              <XAxis
                dataKey="date"
                tickFormatter={(d: string) => formatDateLabel(d, period)}
                tick={{ fill: textColor, fontSize: 10 }}
                axisLine={{ stroke: gridColor }}
                tickLine={false}
                minTickGap={50}
              />

              <YAxis
                tickFormatter={formatDollar}
                tick={{ fill: textColor, fontSize: 10 }}
                axisLine={false}
                tickLine={false}
                domain={yDomain}
                width={60}
              />

              <Tooltip
                content={
                  <ChartTooltip isDark={isDark} initialCapital={initialCapital} />
                }
                cursor={{
                  stroke: textColor,
                  strokeWidth: 1,
                  strokeDasharray: "4 4",
                }}
              />

              {/* Reference line at initial capital */}
              {initialCapital > 0 && (
                <ReferenceLine
                  y={initialCapital}
                  stroke={textColor}
                  strokeDasharray="6 4"
                  strokeOpacity={0.4}
                />
              )}

              <Area
                type="monotone"
                dataKey="equity"
                stroke={strokeColor}
                strokeWidth={2}
                fill={`url(#${gradientId})`}
                dot={false}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        )}
      </div>
    </div>
  );
}
