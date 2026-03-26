"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Activity, TrendingDown } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface DrawdownStatus {
  level: string;
  daily_pnl_pct: number;
  weekly_pnl_pct: number;
  size_multiplier: number;
  restrictions: string[];
  thresholds: {
    drawdown_reduce_pct?: number;
    drawdown_halt_pct?: number;
    drawdown_kill_pct?: number;
    weekly_drawdown_kill_pct?: number;
    reduce?: number;
    halt?: number;
    daily_kill?: number;
    weekly_kill?: number;
  };
}

const TIER_CONFIG = [
  { key: "TIER 1", label: "Tier 1", threshold: -2, action: "Reduce size", color: "#facc15" },
  { key: "TIER 2", label: "Tier 2", threshold: -4, action: "Halt new", color: "#f97316" },
  { key: "TIER 3", label: "Tier 3", threshold: -7, action: "Daily kill", color: "#ef4444" },
  { key: "TIER 4", label: "Tier 4", threshold: -10, action: "Weekly kill", color: "#ef4444" },
] as const;

function getLevelBadgeVariant(level: string): "success" | "warning" | "danger" {
  if (level === "NORMAL") return "success";
  if (level === "TIER 1") return "warning";
  return "danger";
}

function getBarColor(pct: number): string {
  if (pct >= -2) return "#4ade80";
  if (pct >= -4) return "#facc15";
  if (pct >= -7) return "#f97316";
  return "#ef4444";
}

function DrawdownBarSkeleton() {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <div className="app-skeleton h-2.5 w-24 rounded-full" />
        <div className="app-skeleton h-2.5 w-10 rounded-full" />
      </div>
      <div className="app-skeleton h-2.5 w-full rounded-full" />
      <div className="h-3" />
    </div>
  );
}

function DrawdownBar({
  label,
  pct,
  thresholds,
  animate,
}: {
  label: string;
  pct: number;
  thresholds: number[];
  animate?: boolean;
}) {
  const maxRange = 12;
  const fillPct = Math.min(Math.abs(pct) / maxRange, 1) * 100;
  const barColor = getBarColor(pct);
  const [displayWidth, setDisplayWidth] = useState(animate ? 0 : fillPct);

  useEffect(() => {
    if (animate) {
      const raf = requestAnimationFrame(() => setDisplayWidth(fillPct));
      return () => cancelAnimationFrame(raf);
    } else {
      setDisplayWidth(fillPct);
    }
  }, [fillPct, animate]);

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
          {label}
        </span>
        <span
          className="text-xs font-mono font-semibold tabular-nums transition-colors duration-300"
          style={{ color: barColor }}
        >
          {pct.toFixed(2)}%
        </span>
      </div>
      <div className="relative">
        <div className="app-progress-track h-2.5">
          <div
            className="app-progress-bar h-full"
            style={{
              width: `${displayWidth}%`,
              backgroundColor: barColor,
              transition: animate
                ? "width 600ms cubic-bezier(0.4, 0, 0.2, 1), background-color 300ms ease"
                : "background-color 300ms ease",
            }}
          />
        </div>
      </div>
      {/* Tick marks */}
      <div className="relative h-3">
        {thresholds.map((t) => {
          const pos = (Math.abs(t) / maxRange) * 100;
          return (
            <div
              key={t}
              className="absolute flex flex-col items-center"
              style={{ left: `${pos}%`, transform: "translateX(-50%)" }}
            >
              <div className="w-px h-1.5 bg-muted-foreground/30" />
              <span className="text-[8px] font-mono text-muted-foreground/50 mt-0.5">
                {t}%
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function DrawdownMonitor() {
  const [data, setData] = useState<DrawdownStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mounted, setMounted] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<DrawdownStatus>("/api/risk/drawdown-status");
      setData(result);
      setError(false);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (!loading && data) {
      const raf = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(raf);
    }
  }, [loading, data]);

  if (loading) {
    return (
      <Surface>
        <SurfaceHeader>
          <div className="flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Drawdown Monitor</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody className="p-3 space-y-3">
          {/* P&L row skeleton */}
          <div className="flex items-center gap-3">
            <div className="app-skeleton h-3 w-32 rounded-full" />
            <div className="w-px h-3 bg-border" />
            <div className="app-skeleton h-3 w-28 rounded-full" />
          </div>
          <DrawdownBarSkeleton />
          <DrawdownBarSkeleton />
          {/* Tier grid skeleton */}
          <div className="grid grid-cols-2 gap-1.5">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="app-skeleton h-7 rounded-md" />
            ))}
          </div>
        </SurfaceBody>
      </Surface>
    );
  }

  if (error || !data) {
    return (
      <Surface>
        <SurfaceHeader>
          <div className="flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Drawdown Monitor</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody>
          <div className="app-empty">
            <div className="app-empty-icon">
              <TrendingDown className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">No drawdown data</p>
            <p className="text-[11px] text-muted-foreground/60">Backend may be offline</p>
          </div>
        </SurfaceBody>
      </Surface>
    );
  }

  const t = data.thresholds || {};
  const thresholds = [
    t.drawdown_reduce_pct ?? t.reduce ?? -2,
    t.drawdown_halt_pct ?? t.halt ?? -4,
    t.drawdown_kill_pct ?? t.daily_kill ?? -7,
    t.weekly_drawdown_kill_pct ?? t.weekly_kill ?? -10,
  ];
  const isActive = data.level !== "NORMAL";

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <TrendingDown className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Drawdown Monitor</SurfaceTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={getLevelBadgeVariant(data.level)}>
              {isActive && (
                <span
                  className="mr-1 inline-block h-1.5 w-1.5 rounded-full animate-pulse-dot"
                  style={{ backgroundColor: "currentColor" }}
                />
              )}
              {data.level}
            </Badge>
            <span className="text-xs font-mono font-semibold text-foreground tabular-nums">
              {data.size_multiplier}x
            </span>
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-3">
        {/* P&L Summary Row */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <Activity className="h-3 w-3 text-muted-foreground" />
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Daily
            </span>
            <span
              className="text-xs font-mono font-semibold tabular-nums transition-colors duration-300"
              style={{ color: data.daily_pnl_pct >= 0 ? "#4ade80" : getBarColor(data.daily_pnl_pct) }}
            >
              {data.daily_pnl_pct >= 0 ? "+" : ""}
              {data.daily_pnl_pct.toFixed(2)}%
            </span>
          </div>
          <div className="w-px h-3 bg-border" />
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Weekly
            </span>
            <span
              className="text-xs font-mono font-semibold tabular-nums transition-colors duration-300"
              style={{ color: data.weekly_pnl_pct >= 0 ? "#4ade80" : getBarColor(data.weekly_pnl_pct) }}
            >
              {data.weekly_pnl_pct >= 0 ? "+" : ""}
              {data.weekly_pnl_pct.toFixed(2)}%
            </span>
          </div>
          <div className="w-px h-3 bg-border" />
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
              Size
            </span>
            <span className="text-xs font-mono font-semibold tabular-nums text-foreground">
              {data.size_multiplier}x
            </span>
          </div>
        </div>

        {/* Drawdown Bars */}
        <DrawdownBar
          label="Daily Drawdown"
          pct={data.daily_pnl_pct}
          thresholds={thresholds}
          animate={mounted}
        />
        <DrawdownBar
          label="Weekly Drawdown"
          pct={data.weekly_pnl_pct}
          thresholds={thresholds}
          animate={mounted}
        />

        {/* Tier Legend - 2x2 grid */}
        <div className="grid grid-cols-2 gap-1.5">
          {TIER_CONFIG.map((tier) => {
            const isTierActive = tier.key === data.level;
            return (
              <div
                key={tier.key}
                className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-all duration-200"
                style={{
                  backgroundColor: isTierActive ? `${tier.color}18` : "transparent",
                  borderLeft: isTierActive
                    ? `2px solid ${tier.color}`
                    : "2px solid transparent",
                  opacity: isTierActive ? 1 : 0.65,
                }}
              >
                <div
                  className="h-2 w-2 rounded-full shrink-0 transition-all duration-200"
                  style={{
                    backgroundColor: tier.color,
                    boxShadow: isTierActive ? `0 0 6px ${tier.color}80` : "none",
                  }}
                />
                <div className="min-w-0">
                  <span className="text-[10px] font-semibold text-foreground">
                    {tier.label}
                  </span>
                  <span className="text-[9px] text-muted-foreground ml-1">
                    {tier.threshold}% {tier.action}
                  </span>
                </div>
              </div>
            );
          })}
        </div>

        {/* Active restrictions */}
        {(data.restrictions ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {(data.restrictions ?? []).map((r) => (
              <Badge key={r} variant="danger" className="text-[9px] py-0.5 px-2">
                {r}
              </Badge>
            ))}
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
