"use client";

import React, { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Shield, Layers, Gauge, GitBranch } from "lucide-react";
import { cn } from "@/lib/utils";
import { useThemeMode } from "@/hooks/useThemeMode";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface RiskExposurePoint {
  date: string;
  exposure: number; // 0-100
}

interface PortfolioRiskDashPanelProps {
  totalExposure?: number; // 0-1
  sectorConcentration?: number; // HHI 0-1
  riskBudgetUsed?: number; // 0-1
  correlationRisk?: "low" | "medium" | "high";
  exposureHistory?: RiskExposurePoint[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLORS = {
  primary: "hsl(213 96% 63%)",
  primaryFill: "hsla(213, 96%, 63%, 0.12)",
  gridLight: "#e2e8f0",
  gridDark: "#1e293b",
  textLight: "#475569",
  textDark: "#94a3b8",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatExposureColor(value: number): string {
  if (value > 0.8) return "text-red-400";
  if (value >= 0.5) return "text-amber-400";
  return "text-emerald-400";
}

function formatHHI(value: number): string {
  return (value * 10000).toFixed(0);
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(1)}%`;
}

function correlationBadgeClasses(
  risk: "low" | "medium" | "high",
): string {
  switch (risk) {
    case "low":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/20";
    case "medium":
      return "bg-amber-500/15 text-amber-400 border-amber-500/20";
    case "high":
      return "bg-red-500/15 text-red-400 border-red-500/20";
  }
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

// ---------------------------------------------------------------------------
// Metric card
// ---------------------------------------------------------------------------

interface MetricCardProps {
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  children: React.ReactNode;
}

function MetricCard({ label, icon: Icon, children }: MetricCardProps) {
  return (
    <div className="flex flex-col gap-1.5 rounded-lg bg-foreground/[0.03] p-3">
      <div className="flex items-center gap-1.5">
        <Icon className="h-3 w-3 text-muted-foreground/50" />
        <span className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
          {label}
        </span>
      </div>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Tooltip
// ---------------------------------------------------------------------------

interface TooltipPayloadEntry {
  value: number;
}

interface ChartTooltipProps {
  active?: boolean;
  payload?: TooltipPayloadEntry[];
  label?: string;
  isDark: boolean;
}

function ChartTooltip({ active, payload, label, isDark }: ChartTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-2 text-xs shadow-lg",
        isDark
          ? "border-white/10 bg-[#0f1729]"
          : "border-gray-200 bg-white",
      )}
    >
      <p className="mb-0.5 font-medium text-muted-foreground">
        {label ? formatDate(label) : ""}
      </p>
      <p style={{ color: COLORS.primary }}>
        Exposure: {payload[0].value.toFixed(1)}%
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PortfolioRiskDashPanel({
  totalExposure,
  sectorConcentration,
  riskBudgetUsed,
  correlationRisk,
  exposureHistory,
}: PortfolioRiskDashPanelProps) {
  const { isDark } = useThemeMode();

  const textColor = isDark ? COLORS.textDark : COLORS.textLight;

  const hasData =
    totalExposure != null ||
    sectorConcentration != null ||
    riskBudgetUsed != null ||
    correlationRisk != null;

  const budgetPercent = useMemo(
    () => Math.min((riskBudgetUsed ?? 0) * 100, 100),
    [riskBudgetUsed],
  );

  const budgetBarColor = useMemo(() => {
    if (budgetPercent > 80) return "bg-red-400";
    if (budgetPercent >= 50) return "bg-amber-400";
    return "bg-emerald-400";
  }, [budgetPercent]);

  // Empty state
  if (!hasData && (!exposureHistory || exposureHistory.length === 0)) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-center">
          <Shield className="h-8 w-8 text-muted-foreground/30" />
          <p className="text-sm text-muted-foreground">
            Risk metrics will appear once positions are open.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col gap-4">
      {/* 2x2 metric grid */}
      <div className="grid grid-cols-2 gap-2">
        {/* Total Exposure */}
        <MetricCard label="Total Exposure" icon={Shield}>
          <span
            className={cn(
              "text-lg font-mono font-bold tabular-nums",
              totalExposure != null
                ? formatExposureColor(totalExposure)
                : "text-muted-foreground",
            )}
          >
            {totalExposure != null ? formatPercent(totalExposure) : "--"}
          </span>
        </MetricCard>

        {/* Sector Concentration */}
        <MetricCard label="Sector HHI" icon={Layers}>
          <span className="text-lg font-mono font-bold tabular-nums text-foreground">
            {sectorConcentration != null
              ? formatHHI(sectorConcentration)
              : "--"}
          </span>
        </MetricCard>

        {/* Risk Budget Used */}
        <MetricCard label="Risk Budget" icon={Gauge}>
          <div className="flex flex-col gap-1.5">
            <span className="text-lg font-mono font-bold tabular-nums text-foreground">
              {riskBudgetUsed != null ? formatPercent(riskBudgetUsed) : "--"}
            </span>
            {riskBudgetUsed != null && (
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-foreground/10">
                <div
                  className={cn("h-full rounded-full transition-all", budgetBarColor)}
                  style={{ width: `${budgetPercent}%` }}
                />
              </div>
            )}
          </div>
        </MetricCard>

        {/* Correlation Risk */}
        <MetricCard label="Correlation" icon={GitBranch}>
          {correlationRisk != null ? (
            <span
              className={cn(
                "inline-flex w-fit items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold capitalize",
                correlationBadgeClasses(correlationRisk),
              )}
            >
              {correlationRisk}
            </span>
          ) : (
            <span className="text-lg font-mono font-bold tabular-nums text-muted-foreground">
              --
            </span>
          )}
        </MetricCard>
      </div>

      {/* Exposure history chart */}
      {exposureHistory && exposureHistory.length > 0 && (
        <div className="min-h-0 flex-1">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart
              data={exposureHistory}
              margin={{ top: 4, right: 4, bottom: 0, left: 0 }}
            >
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                tick={{ fill: textColor, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                minTickGap={40}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fill: textColor, fontSize: 9 }}
                axisLine={false}
                tickLine={false}
                tickFormatter={(v: number) => `${v}%`}
                width={36}
              />
              <Tooltip
                content={<ChartTooltip isDark={isDark} />}
                cursor={{
                  stroke: textColor,
                  strokeWidth: 1,
                  strokeDasharray: "4 4",
                }}
              />
              <Area
                type="monotone"
                dataKey="exposure"
                stroke={COLORS.primary}
                strokeWidth={1.5}
                fill={COLORS.primaryFill}
                fillOpacity={1}
                isAnimationActive={false}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
