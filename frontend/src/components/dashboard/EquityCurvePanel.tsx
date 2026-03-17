"use client";

import React, { useMemo } from "react";
import {
  ComposedChart,
  Line,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { TrendingUp } from "lucide-react";
import { cn } from "@/lib/utils";
import { useThemeMode } from "@/hooks/useThemeMode";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface EquityPoint {
  date: string;
  equity: number;
  drawdown: number; // 0 to -X (negative)
  benchmark?: number; // SPY comparison
}

interface EquityCurvePanelProps {
  data?: EquityPoint[];
  showBenchmark?: boolean;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLORS = {
  equity: "hsl(213 96% 63%)",
  drawdownStroke: "#ef4444",
  drawdownFill: "rgba(239, 68, 68, 0.15)",
  benchmark: "#64748b",
  gridLight: "#e2e8f0",
  gridDark: "#1e293b",
  textLight: "#475569",
  textDark: "#94a3b8",
};

// ---------------------------------------------------------------------------
// Formatters
// ---------------------------------------------------------------------------

function formatDollar(value: number): string {
  if (value >= 1_000_000) return `$${(value / 1_000_000).toFixed(1)}M`;
  if (value >= 1_000) return `$${(value / 1_000).toFixed(1)}K`;
  return `$${value.toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Custom tooltip
// ---------------------------------------------------------------------------

interface TooltipPayloadEntry {
  dataKey: string;
  value: number;
  color: string;
}

interface CustomTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  isDark: boolean;
}

function ChartTooltip({ active, payload, label, isDark }: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  const equityEntry = payload.find((p) => p.dataKey === "equity");
  const drawdownEntry = payload.find((p) => p.dataKey === "drawdown");
  const benchmarkEntry = payload.find((p) => p.dataKey === "benchmark");

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-xs shadow-lg",
        isDark
          ? "border-white/10 bg-[#0f1729]"
          : "border-gray-200 bg-white",
      )}
    >
      <p className="mb-1 font-medium text-muted-foreground">
        {label ? formatDate(label) : ""}
      </p>
      {equityEntry && (
        <p style={{ color: COLORS.equity }}>
          Equity: {formatDollar(equityEntry.value)}
        </p>
      )}
      {drawdownEntry && (
        <p style={{ color: COLORS.drawdownStroke }}>
          Drawdown: {drawdownEntry.value.toFixed(2)}%
        </p>
      )}
      {benchmarkEntry && (
        <p style={{ color: COLORS.benchmark }}>
          SPY: {formatDollar(benchmarkEntry.value)}
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function EquityCurvePanel({
  data,
  showBenchmark = false,
}: EquityCurvePanelProps) {
  const { isDark } = useThemeMode();

  const gridColor = isDark ? COLORS.gridDark : COLORS.gridLight;
  const textColor = isDark ? COLORS.textDark : COLORS.textLight;

  const yDomain = useMemo(() => {
    if (!data || data.length === 0) return [0, 100];
    const values = data.map((d) => d.equity);
    if (showBenchmark) {
      data.forEach((d) => {
        if (d.benchmark != null) values.push(d.benchmark);
      });
    }
    const min = Math.min(...values);
    const max = Math.max(...values);
    const padding = (max - min) * 0.05 || 100;
    return [Math.floor(min - padding), Math.ceil(max + padding)];
  }, [data, showBenchmark]);

  // Empty state
  if (!data || data.length === 0) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-center">
          <TrendingUp className="h-8 w-8 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">
            Equity curve will appear after your first trade.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 8, bottom: 0, left: 0 }}
        >
          <CartesianGrid
            strokeDasharray="3 3"
            stroke={gridColor}
            vertical={false}
          />

          <XAxis
            dataKey="date"
            tickFormatter={formatDate}
            tick={{ fill: textColor, fontSize: 10 }}
            axisLine={{ stroke: gridColor }}
            tickLine={false}
            minTickGap={40}
          />

          <YAxis
            yAxisId="equity"
            tickFormatter={formatDollar}
            tick={{ fill: textColor, fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            domain={yDomain}
            width={60}
          />

          <YAxis
            yAxisId="drawdown"
            orientation="right"
            tickFormatter={(v: number) => `${v.toFixed(0)}%`}
            tick={{ fill: textColor, fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            domain={[(dataMin: number) => Math.min(dataMin, -1), 0]}
            width={48}
          />

          <Tooltip
            content={<ChartTooltip isDark={isDark} />}
            cursor={{ stroke: textColor, strokeWidth: 1, strokeDasharray: "4 4" }}
          />

          {/* Drawdown area (behind equity line) */}
          <Area
            yAxisId="drawdown"
            type="monotone"
            dataKey="drawdown"
            stroke={COLORS.drawdownStroke}
            strokeWidth={1}
            fill={COLORS.drawdownFill}
            fillOpacity={1}
            isAnimationActive={false}
          />

          {/* SPY benchmark */}
          {showBenchmark && (
            <Line
              yAxisId="equity"
              type="monotone"
              dataKey="benchmark"
              stroke={COLORS.benchmark}
              strokeWidth={1.5}
              strokeDasharray="6 3"
              dot={false}
              isAnimationActive={false}
            />
          )}

          {/* Equity line (on top) */}
          <Line
            yAxisId="equity"
            type="monotone"
            dataKey="equity"
            stroke={COLORS.equity}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
