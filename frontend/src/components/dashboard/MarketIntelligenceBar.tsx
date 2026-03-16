"use client";

import React from "react";
import {
  TrendingUp,
  TrendingDown,
  Activity,
  Brain,
  Zap,
  BarChart3,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface MarketIntelligenceBarProps {
  trend?: { direction: "bullish" | "bearish" | "sideways"; label: string };
  volatility?: { vix: number; level: "low" | "moderate" | "high" };
  sentiment?: "risk-on" | "risk-off" | "neutral";
  bestSector?: string;
  strategyStatus?: { active: boolean; name?: string };
}

const TREND_CONFIG: Record<
  "bullish" | "bearish" | "sideways",
  { symbol: string; color: string; icon: React.ElementType }
> = {
  bullish: { symbol: "\u2191", color: "text-emerald-400", icon: TrendingUp },
  bearish: { symbol: "\u2193", color: "text-red-400", icon: TrendingDown },
  sideways: { symbol: "\u2192", color: "text-amber-400", icon: Activity },
};

const VOLATILITY_COLOR: Record<"low" | "moderate" | "high", string> = {
  low: "text-emerald-400",
  moderate: "text-amber-400",
  high: "text-red-400",
};

const SENTIMENT_CONFIG: Record<
  "risk-on" | "risk-off" | "neutral",
  { label: string; color: string }
> = {
  "risk-on": { label: "Risk-On", color: "text-emerald-400" },
  "risk-off": { label: "Risk-Off", color: "text-red-400" },
  neutral: { label: "Neutral", color: "text-amber-400" },
};

function Segment({
  title,
  value,
  valueColor,
  dimmed = false,
}: {
  title: string;
  value: React.ReactNode;
  valueColor?: string;
  dimmed?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center gap-0.5 min-w-0", dimmed && "opacity-40")}>
      <span className="text-[9px] uppercase tracking-widest text-muted-foreground whitespace-nowrap">
        {title}
      </span>
      <span
        className={cn(
          "text-xs font-semibold whitespace-nowrap",
          valueColor || "text-foreground"
        )}
      >
        {value}
      </span>
    </div>
  );
}

export function MarketIntelligenceBar({
  trend,
  volatility,
  sentiment,
  bestSector,
  strategyStatus,
}: MarketIntelligenceBarProps) {
  const trendConfig = trend ? TREND_CONFIG[trend.direction] : null;
  const volColor = volatility ? VOLATILITY_COLOR[volatility.level] : null;
  const sentimentConfig = sentiment ? SENTIMENT_CONFIG[sentiment] : null;

  return (
    <div
      className="flex h-12 items-center justify-between gap-8 rounded-xl border px-3"
      style={{
        background: "hsl(var(--surface-1))",
        borderColor: "hsl(var(--border) / 0.6)",
      }}
    >
      {/* Market Trend */}
      {trend && trendConfig ? (
        <Segment
          title="Market Trend"
          value={
            <span className="flex items-center gap-1">
              <trendConfig.icon className="h-3 w-3" />
              {trend.label} {trendConfig.symbol}
            </span>
          }
          valueColor={trendConfig.color}
        />
      ) : (
        <Segment title="Market Trend" value="--" dimmed />
      )}

      {/* Volatility */}
      {volatility && volColor ? (
        <Segment
          title="Volatility"
          value={`VIX: ${volatility.vix.toFixed(1)} (${volatility.level.charAt(0).toUpperCase() + volatility.level.slice(1)})`}
          valueColor={volColor}
        />
      ) : (
        <Segment title="Volatility" value="--" dimmed />
      )}

      {/* Sentiment */}
      {sentiment && sentimentConfig ? (
        <Segment
          title="Sentiment"
          value={sentimentConfig.label}
          valueColor={sentimentConfig.color}
        />
      ) : (
        <Segment title="Sentiment" value="--" dimmed />
      )}

      {/* Best Sector */}
      {bestSector ? (
        <Segment
          title="Best Sector"
          value={
            <span className="flex items-center gap-1">
              <BarChart3 className="h-3 w-3 text-muted-foreground" />
              {bestSector}
            </span>
          }
          valueColor="text-foreground"
        />
      ) : (
        <Segment title="Best Sector" value="--" dimmed />
      )}

      {/* Strategy Status */}
      {strategyStatus ? (
        <Segment
          title="Strategy"
          value={
            strategyStatus.active ? (
              <span className="flex items-center gap-1">
                <Zap className="h-3 w-3" />
                Active {strategyStatus.name ? `\u2014 ${strategyStatus.name}` : ""}
              </span>
            ) : (
              "Idle"
            )
          }
          valueColor={strategyStatus.active ? "text-emerald-400" : "text-muted-foreground"}
        />
      ) : (
        <Segment title="Strategy" value="--" dimmed />
      )}
    </div>
  );
}
