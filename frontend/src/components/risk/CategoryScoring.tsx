"use client";

import React, { useEffect, useState, useCallback } from "react";
import { BarChart3, ShieldOff } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface CategoryScore {
  strategy_type: string;
  score: number;
  // API fields
  roi_component?: number;
  win_rate_component?: number;
  total_trades?: number;
  is_blocked?: boolean;
  // Legacy fields (kept for compatibility)
  win_rate?: number;
  roi?: number;
  num_trades?: number;
  status?: string;
}

interface CategoryScoresResponse {
  scores: CategoryScore[];
  count: number;
  blocked_count: number;
}

function getScoreColor(score: number): string {
  if (score >= 60) return "#4ade80";
  if (score >= 30) return "#facc15";
  return "#ef4444";
}

function formatStrategyName(name: string): string {
  return name
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function ScoreRowSkeleton() {
  return (
    <div className="space-y-1.5 py-0.5">
      <div className="flex items-center justify-between gap-2">
        <div className="app-skeleton h-3 w-36 rounded-full" />
        <div className="app-skeleton h-3 w-12 rounded-full" />
      </div>
      <div className="app-skeleton h-2 w-full rounded-full" />
      <div className="app-skeleton h-2 w-40 rounded-full" />
    </div>
  );
}

function ScoreRow({
  cat,
  animate,
}: {
  cat: CategoryScore;
  animate: boolean;
}) {
  const isBlocked = cat.is_blocked ?? cat.score < 30;
  const scoreColor = getScoreColor(cat.score);
  const fillPct = Math.min(cat.score, 100);
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
    <div
      className="space-y-1 transition-opacity duration-200"
      style={{ opacity: isBlocked ? 0.6 : 1 }}
    >
      {/* Name + Badge + Score */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-semibold text-foreground truncate">
            {formatStrategyName(cat.strategy_type)}
          </span>
          {isBlocked && (
            <span className="inline-flex items-center gap-1 rounded-full bg-red-500/15 border border-red-500/25 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-red-400 shrink-0">
              <ShieldOff className="h-2.5 w-2.5" />
              Blocked
            </span>
          )}
        </div>
        <span
          className="text-xs font-mono font-semibold tabular-nums shrink-0 transition-colors duration-300"
          style={{ color: scoreColor }}
        >
          {cat.score}/100
        </span>
      </div>

      {/* Progress bar */}
      <div className="app-progress-track h-2">
        <div
          className="app-progress-bar h-full"
          style={{
            width: `${displayWidth}%`,
            backgroundColor: scoreColor,
            transition: animate
              ? "width 600ms cubic-bezier(0.4, 0, 0.2, 1), background-color 300ms ease"
              : "background-color 300ms ease",
          }}
        />
      </div>

      {/* Stats line */}
      {(() => {
        const numTrades = cat.total_trades ?? cat.num_trades ?? 0;
        const winRatePct = (cat.win_rate_component != null ? cat.win_rate_component : (cat.win_rate ?? 0)) * (cat.win_rate_component != null ? 100 / Math.max(cat.score, 1) : 100);
        const roiVal = cat.roi_component ?? cat.roi ?? 0;
        return (
          <div className="flex items-center gap-2 text-[9px] text-muted-foreground font-mono">
            <span>{numTrades} trades</span>
            <span className="text-muted-foreground/30">|</span>
            <span>{roiVal >= 0 ? "+" : ""}{roiVal.toFixed(1)}% ROI</span>
            <span className="text-muted-foreground/30">|</span>
            <span>Score: {cat.score.toFixed(0)}/100</span>
          </div>
        );
      })()}
    </div>
  );
}

export function CategoryScoring() {
  const [data, setData] = useState<CategoryScoresResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mounted, setMounted] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<CategoryScoresResponse>(
        "/api/risk/category-scores"
      );
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
    const interval = setInterval(fetchData, 30000);
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
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Strategy Category Scoring</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody className="p-3 space-y-3">
          {[0, 1, 2, 3].map((i) => (
            <ScoreRowSkeleton key={i} />
          ))}
        </SurfaceBody>
      </Surface>
    );
  }

  if (error || !data) {
    return (
      <Surface>
        <SurfaceHeader>
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Strategy Category Scoring</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody>
          <div className="app-empty">
            <div className="app-empty-icon">
              <BarChart3 className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">Scoring data unavailable</p>
            <p className="text-[11px] text-muted-foreground/60">Backend may be offline</p>
          </div>
        </SurfaceBody>
      </Surface>
    );
  }

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Strategy Category Scoring</SurfaceTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="neutral" className="text-[9px] py-0.5">
              Blocked below 30 / 100
            </Badge>
            {(data.blocked_count ?? 0) > 0 && (
              <Badge variant="danger" className="text-[9px] py-0.5">
                {data.blocked_count} blocked
              </Badge>
            )}
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-2.5">
        {(data.scores ?? []).length === 0 ? (
          <div className="app-empty">
            <div className="app-empty-icon">
              <BarChart3 className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">No category scores yet</p>
            <p className="text-[11px] text-muted-foreground/60">
              Scores appear after strategies run their first trades
            </p>
          </div>
        ) : (
          (data.scores ?? []).map((cat) => (
            <ScoreRow key={cat.strategy_type} cat={cat} animate={mounted} />
          ))
        )}
      </SurfaceBody>
    </Surface>
  );
}
