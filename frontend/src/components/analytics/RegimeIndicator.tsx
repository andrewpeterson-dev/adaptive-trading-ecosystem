"use client";

import React from "react";
import {
  TrendingUp,
  TrendingDown,
  Minus,
  Activity,
  Zap,
} from "lucide-react";
import type { RegimeData } from "@/types/models";

const REGIME_CONFIG: Record<string, { label: string; color: string; bgColor: string; borderColor: string; icon: React.ElementType }> = {
  low_vol_bull: { label: "Low Vol Bull", color: "text-emerald-400", bgColor: "bg-emerald-400/10", borderColor: "border-emerald-400/30", icon: TrendingUp },
  high_vol_bull: { label: "High Vol Bull", color: "text-purple-400", bgColor: "bg-purple-400/10", borderColor: "border-purple-400/30", icon: Zap },
  low_vol_bear: { label: "Low Vol Bear", color: "text-red-400", bgColor: "bg-red-400/10", borderColor: "border-red-400/30", icon: TrendingDown },
  high_vol_bear: { label: "High Vol Bear", color: "text-red-500", bgColor: "bg-red-500/10", borderColor: "border-red-500/30", icon: Zap },
  sideways: { label: "Sideways", color: "text-amber-400", bgColor: "bg-amber-400/10", borderColor: "border-amber-400/30", icon: Minus },
};

export function RegimeIndicator({ data }: { data: RegimeData | null }) {
  if (!data) return null;

  const config = REGIME_CONFIG[data.regime] || REGIME_CONFIG.sideways;
  const Icon = config.icon;
  const hasTrend = data.trend_strength != null;
  const hasVol = data.volatility_20d != null;
  const trendPct = hasTrend ? Math.min(Math.abs(data.trend_strength!) * 10000, 100) : 0;
  const trendDirection = (data.trend_strength ?? 0) >= 0 ? "Bullish" : "Bearish";

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
        <Activity className="h-4 w-4" />
        Market Regime
      </div>

      <div className="flex items-center gap-3">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md border ${config.bgColor} ${config.borderColor}`}>
          <Icon className={`h-4 w-4 ${config.color}`} />
          <span className={`text-sm font-bold ${config.color}`}>{config.label}</span>
        </div>
        <span className="text-xs text-muted-foreground font-mono tabular-nums">
          {(data.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Volatility (20d)</div>
          <div className="text-sm font-mono tabular-nums">
            {hasVol ? `${(data.volatility_20d! * 100).toFixed(1)}%` : <span className="text-muted-foreground/50">N/A</span>}
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
            <div
              className="h-full rounded-full bg-purple-500"
              style={{ width: `${Math.min((data.vol_percentile || 0) * 100, 100)}%` }}
            />
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Trend ({trendDirection})</div>
          {hasTrend ? (
            <div className="flex items-center gap-1">
              {(data.trend_strength ?? 0) >= 0 ? (
                <TrendingUp className="h-3 w-3 text-emerald-400" />
              ) : (
                <TrendingDown className="h-3 w-3 text-red-400" />
              )}
              <span className="text-sm font-mono tabular-nums">{(data.trend_strength! * 10000).toFixed(2)}</span>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground/50">N/A</span>
          )}
          <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
            <div
              className={`h-full rounded-full ${(data.trend_strength ?? 0) >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
              style={{ width: `${trendPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
