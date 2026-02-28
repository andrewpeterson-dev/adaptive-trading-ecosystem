"use client";

import React from "react";
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

interface EquityCurveChartProps {
  data: { date: string; value: number }[];
  initialCapital?: number;
  height?: number;
}

export function EquityCurveChart({ data, initialCapital, height = 300 }: EquityCurveChartProps) {
  if (!data || data.length === 0) {
    return (
      <div className="rounded-lg border bg-card p-6 flex items-center justify-center text-muted-foreground text-sm" style={{ height }}>
        No equity data available
      </div>
    );
  }

  const formatCurrency = (val: number) => {
    if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(1)}M`;
    if (val >= 1_000) return `$${(val / 1_000).toFixed(0)}k`;
    return `$${val.toFixed(0)}`;
  };

  const finalValue = data[data.length - 1]?.value ?? 0;
  const startValue = initialCapital ?? data[0]?.value ?? 0;
  const totalReturn = startValue > 0 ? ((finalValue - startValue) / startValue) * 100 : 0;
  const isPositive = totalReturn >= 0;

  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
          Equity Curve
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono font-medium">{formatCurrency(finalValue)}</span>
          <span
            className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
              isPositive
                ? "text-emerald-400 bg-emerald-400/10"
                : "text-red-400 bg-red-400/10"
            }`}
          >
            {isPositive ? "+" : ""}
            {totalReturn.toFixed(1)}%
          </span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={height}>
        <AreaChart data={data}>
          <defs>
            <linearGradient id="equityGradient" x1="0" y1="0" x2="0" y2="1">
              <stop offset="5%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0.3} />
              <stop offset="95%" stopColor={isPositive ? "#10b981" : "#ef4444"} stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis
            dataKey="date"
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            interval="preserveStartEnd"
            tickFormatter={(d: string) => d.slice(5)}
          />
          <YAxis
            width={60}
            tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            tickFormatter={formatCurrency}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              fontSize: "12px",
            }}
            formatter={(val) => [`$${Number(val ?? 0).toLocaleString()}`, "Equity"]}
          />
          {initialCapital && (
            <ReferenceLine
              y={initialCapital}
              stroke="hsl(var(--muted-foreground))"
              strokeDasharray="6 4"
              label={{ value: "Initial", position: "left", fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
            />
          )}
          <Area
            type="monotone"
            dataKey="value"
            stroke={isPositive ? "#10b981" : "#ef4444"}
            fill="url(#equityGradient)"
            strokeWidth={2}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
