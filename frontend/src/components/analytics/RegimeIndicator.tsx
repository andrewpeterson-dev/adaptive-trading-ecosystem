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
  const trendPct = Math.min(Math.abs(data.trend_strength) * 10000, 100);
  const trendDirection = data.trend_strength >= 0 ? "Bullish" : "Bearish";

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
        <Activity className="h-4 w-4" />
        Market Regime
      </div>

      <div className="flex items-center gap-3">
        <div className={`flex items-center gap-2 px-3 py-1.5 rounded-md border ${config.bgColor} ${config.borderColor}`}>
          <Icon className={`h-4 w-4 ${config.color}`} />
          <span className={`text-sm font-bold ${config.color}`}>{config.label}</span>
        </div>
        <span className="text-xs text-muted-foreground font-mono">
          {(data.confidence * 100).toFixed(0)}% confidence
        </span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <div className="text-xs text-muted-foreground mb-1">Volatility (20d)</div>
          <div className="text-sm font-mono">{(data.volatility_20d * 100).toFixed(1)}%</div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
            <div
              className="h-full rounded-full bg-purple-500"
              style={{ width: `${Math.min((data.vol_percentile || 0) * 100, 100)}%` }}
            />
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground mb-1">Trend ({trendDirection})</div>
          <div className="flex items-center gap-1">
            {data.trend_strength >= 0 ? (
              <TrendingUp className="h-3 w-3 text-emerald-400" />
            ) : (
              <TrendingDown className="h-3 w-3 text-red-400" />
            )}
            <span className="text-sm font-mono">{(data.trend_strength * 10000).toFixed(2)}</span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden mt-1">
            <div
              className={`h-full rounded-full ${data.trend_strength >= 0 ? "bg-emerald-500" : "bg-red-500"}`}
              style={{ width: `${trendPct}%` }}
            />
          </div>
        </div>
      </div>
    </div>
  );
}
