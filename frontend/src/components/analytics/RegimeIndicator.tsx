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
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";

const REGIME_CONFIG: Record<string, { label: string; color: string; bgColor: string; borderColor: string; icon: React.ElementType }> = {
  low_vol_bull: { label: "Low Vol Bull", color: "text-emerald-300", bgColor: "bg-emerald-500/12", borderColor: "border-emerald-500/25", icon: TrendingUp },
  high_vol_bull: { label: "High Vol Bull", color: "text-violet-200", bgColor: "bg-violet-500/12", borderColor: "border-violet-500/25", icon: Zap },
  low_vol_bear: { label: "Low Vol Bear", color: "text-red-200", bgColor: "bg-red-500/12", borderColor: "border-red-500/25", icon: TrendingDown },
  high_vol_bear: { label: "High Vol Bear", color: "text-red-100", bgColor: "bg-red-500/16", borderColor: "border-red-500/30", icon: Zap },
  sideways: { label: "Sideways", color: "text-amber-200", bgColor: "bg-amber-500/12", borderColor: "border-amber-500/25", icon: Minus },
};

export function RegimeIndicator({ data }: { data: RegimeData | null }) {
  if (!data) return null;
  if (!data.regime || data.confidence == null) return null;

  const config = REGIME_CONFIG[data.regime] || REGIME_CONFIG.sideways;
  const Icon = config.icon;
  const hasTrend = data.trend_strength != null;
  const hasVol = data.volatility_20d != null;
  const trendPct = hasTrend ? Math.min(Math.abs(data.trend_strength!) * 10000, 100) : 0;
  const trendDirection = (data.trend_strength ?? 0) >= 0 ? "Bullish" : "Bearish";

  return (
    <div className="app-panel p-5">
      <div className="space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-[0.18em] text-muted-foreground">
        <Activity className="h-4 w-4" />
        Market Regime
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className={`flex items-center gap-2 rounded-full border px-3 py-1.5 ${config.bgColor} ${config.borderColor}`}>
          <Icon className={`h-4 w-4 ${config.color}`} />
          <span className={`text-sm font-bold ${config.color}`}>{config.label}</span>
        </div>
        <Badge className="tracking-normal font-mono">
          {(data.confidence * 100).toFixed(0)}% confidence
        </Badge>
      </div>

      <div className="grid gap-3 rounded-[20px] border border-border/70 bg-muted/30 p-4 md:grid-cols-2">
        <div>
          <div className="mb-1 text-xs text-muted-foreground">Volatility (20d)</div>
          <div className="text-sm font-mono tabular-nums text-foreground">
            {hasVol ? `${(data.volatility_20d! * 100).toFixed(1)}%` : <span className="text-muted-foreground/50">N/A</span>}
          </div>
          <Progress
            className="mt-2"
            value={Math.min((data.vol_percentile || 0) * 100, 100)}
            indicatorClassName="bg-gradient-to-r from-violet-500 via-fuchsia-400 to-sky-400"
          />
        </div>
        <div>
          <div className="mb-1 text-xs text-muted-foreground">Trend ({trendDirection})</div>
          {hasTrend ? (
            <div className="flex items-center gap-1">
              {(data.trend_strength ?? 0) >= 0 ? (
                <TrendingUp className="h-3 w-3 text-emerald-300" />
              ) : (
                <TrendingDown className="h-3 w-3 text-red-300" />
              )}
              <span className="text-sm font-mono tabular-nums text-foreground">{(data.trend_strength! * 10000).toFixed(2)}</span>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground/50">N/A</span>
          )}
          <Progress
            className="mt-2"
            value={trendPct}
            indicatorClassName={(data.trend_strength ?? 0) >= 0 ? "bg-emerald-400" : "bg-red-400"}
          />
        </div>
      </div>
      </div>
    </div>
  );
}
