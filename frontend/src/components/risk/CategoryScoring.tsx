"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Loader2, BarChart3, ShieldOff } from "lucide-react";
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
  win_rate: number;
  roi: number;
  num_trades: number;
  status: string;
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

export function CategoryScoring() {
  const [data, setData] = useState<CategoryScoresResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

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

  if (loading) {
    return (
      <Surface>
        <SurfaceBody className="flex items-center justify-center py-8">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
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
          <p className="text-xs text-muted-foreground text-center py-4">
            Category scoring data unavailable.
          </p>
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
            {data.blocked_count > 0 && (
              <Badge variant="danger" className="text-[9px] py-0.5">
                {data.blocked_count} blocked
              </Badge>
            )}
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-2">
        {data.scores.map((cat) => {
          const isBlocked = cat.score < 30;
          const scoreColor = getScoreColor(cat.score);
          const fillPct = Math.min(cat.score, 100);

          return (
            <div
              key={cat.strategy_type}
              className="space-y-1"
              style={{ opacity: isBlocked ? 0.65 : 1 }}
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
                  className="text-xs font-mono font-semibold tabular-nums shrink-0"
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
                    width: `${fillPct}%`,
                    backgroundColor: scoreColor,
                  }}
                />
              </div>

              {/* Stats line */}
              <div className="flex items-center gap-2 text-[9px] text-muted-foreground font-mono">
                <span>{cat.num_trades} trades</span>
                <span className="text-muted-foreground/30">|</span>
                <span>{(cat.win_rate * 100).toFixed(0)}% win rate</span>
                <span className="text-muted-foreground/30">|</span>
                <span
                  style={{
                    color: cat.roi >= 0 ? "#4ade80" : "#ef4444",
                  }}
                >
                  {cat.roi >= 0 ? "+" : ""}
                  {cat.roi.toFixed(1)}% ROI
                </span>
              </div>
            </div>
          );
        })}

        {data.scores.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No category scores recorded yet.
          </p>
        )}
      </SurfaceBody>
    </Surface>
  );
}
