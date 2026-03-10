"use client";

import React from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Legend,
} from "recharts";

const CATEGORY_COLORS: Record<string, string> = {
  Momentum: "#3b82f6",
  Trend: "#10b981",
  Volatility: "#f59e0b",
  Volume: "#8b5cf6",
};

interface IndicatorChartProps {
  data: number[];
  label: string;
  color?: string;
  category?: string;
  thresholds?: { overbought?: number; oversold?: number };
  multiLine?: Record<string, number[]>;
}

export function IndicatorChart({
  data,
  label,
  color,
  category,
  thresholds,
  multiLine,
}: IndicatorChartProps) {
  const lineColor = color || (category ? CATEGORY_COLORS[category] : "#3b82f6") || "#3b82f6";

  if (multiLine) {
    const keys = Object.keys(multiLine);
    const maxLength = keys.length > 0 ? Math.max(...keys.map((k) => multiLine[k].length)) : 0;
    const chartData = Array.from({ length: maxLength }, (_, i) => {
      const point: Record<string, number> = { index: i };
      for (const key of keys) {
        point[key] = multiLine[key][i] ?? 0;
      }
      return point;
    });

    const colors = ["#3b82f6", "#ef4444", "#f59e0b", "#10b981"];

    return (
      <div className="rounded-lg border border-border/50 bg-card p-3">
        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
          {label}
        </div>
        <ResponsiveContainer width="100%" height={160}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
            <XAxis dataKey="index" hide />
            <YAxis width={40} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
            <Tooltip
              contentStyle={{
                backgroundColor: "hsl(var(--card))",
                border: "1px solid hsl(var(--border))",
                borderRadius: "6px",
                fontSize: "12px",
              }}
            />
            {thresholds?.overbought !== undefined && (
              <ReferenceLine y={thresholds.overbought} stroke="#ef4444" strokeDasharray="4 4" />
            )}
            {thresholds?.oversold !== undefined && (
              <ReferenceLine y={thresholds.oversold} stroke="#10b981" strokeDasharray="4 4" />
            )}
            {keys.map((key, idx) => (
              <Line
                key={key}
                type="monotone"
                dataKey={key}
                stroke={colors[idx % colors.length]}
                dot={false}
                strokeWidth={1.5}
              />
            ))}
            <Legend wrapperStyle={{ fontSize: "10px" }} />
          </LineChart>
        </ResponsiveContainer>
      </div>
    );
  }

  const chartData = data.map((v, i) => ({ index: i, value: v }));

  return (
    <div className="rounded-lg border bg-card p-3">
      <div className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">
        {label}
      </div>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
          <XAxis dataKey="index" hide />
          <YAxis width={40} tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }} />
          <Tooltip
            contentStyle={{
              backgroundColor: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              borderRadius: "6px",
              fontSize: "12px",
            }}
          />
          {thresholds?.overbought !== undefined && (
            <ReferenceLine y={thresholds.overbought} stroke="#ef4444" strokeDasharray="4 4" />
          )}
          {thresholds?.oversold !== undefined && (
            <ReferenceLine y={thresholds.oversold} stroke="#10b981" strokeDasharray="4 4" />
          )}
          <Line type="monotone" dataKey="value" stroke={lineColor} dot={false} strokeWidth={1.5} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
