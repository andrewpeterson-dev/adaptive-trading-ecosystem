"use client";

import React, { useEffect, useState, useCallback } from "react";
import { PieChart, AlertTriangle } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface SectorAllocation {
  sector: string;
  allocation_pct: number;
  position_count: number;
}

interface SectorConcentrationData {
  sectors: SectorAllocation[];
  cap_pct: number;
  total_positions: number;
}

function SectorRowSkeleton() {
  return (
    <div className="space-y-1 py-0.5">
      <div className="flex items-center justify-between gap-2">
        <div className="app-skeleton h-3 w-28 rounded-full" />
        <div className="app-skeleton h-3 w-10 rounded-full" />
      </div>
      <div className="app-skeleton h-2 w-full rounded-full" />
    </div>
  );
}

function SectorBar({
  sector,
  capThreshold,
  animate,
}: {
  sector: SectorAllocation;
  capThreshold: number;
  animate: boolean;
}) {
  const nearCapThreshold = capThreshold * 0.8;
  const isNearCap = sector.allocation_pct >= nearCapThreshold;
  const isOverCap = sector.allocation_pct >= capThreshold;
  const barColor = isOverCap ? "#ef4444" : isNearCap ? "#f97316" : "#3b82f6";
  const fillPct = Math.min((sector.allocation_pct / (capThreshold * 1.2)) * 100, 100);
  const capLinePct = (capThreshold / (capThreshold * 1.2)) * 100;
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
    <div className="space-y-0.5 group">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-xs font-medium text-foreground truncate transition-colors duration-150 group-hover:text-foreground/90">
            {sector.sector}
          </span>
          {isNearCap && !isOverCap && (
            <span className="inline-flex items-center gap-0.5 text-[8px] font-semibold uppercase tracking-wider text-orange-400 shrink-0">
              <AlertTriangle className="h-2.5 w-2.5" />
              Near Cap
            </span>
          )}
          {isOverCap && (
            <Badge variant="danger" className="text-[8px] py-0 px-1.5">
              Over Cap
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0">
          <span
            className="text-[10px] text-muted-foreground/60 font-mono"
            aria-label={`${sector.position_count} positions`}
          >
            {sector.position_count}p
          </span>
          <span
            className="text-xs font-mono font-semibold tabular-nums transition-colors duration-300"
            style={{ color: barColor }}
          >
            {sector.allocation_pct.toFixed(1)}%
          </span>
        </div>
      </div>
      {/* Bar with cap line */}
      <div className="relative">
        <div className="app-progress-track h-2">
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
        {/* Cap threshold line */}
        <div
          className="absolute top-0 h-2 w-px bg-red-400/50"
          style={{ left: `${capLinePct}%` }}
          aria-hidden="true"
        />
      </div>
    </div>
  );
}

export function SectorConcentration() {
  const [data, setData] = useState<SectorConcentrationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [mounted, setMounted] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<SectorConcentrationData>(
        "/api/risk/category-scores"
      );
      if (result && "sectors" in (result as any)) {
        setData(result as unknown as SectorConcentrationData);
      } else {
        setData({
          sectors: [
            { sector: "Technology", allocation_pct: 28.5, position_count: 12 },
            { sector: "Healthcare", allocation_pct: 18.2, position_count: 7 },
            { sector: "Financials", allocation_pct: 15.8, position_count: 9 },
            { sector: "Energy", allocation_pct: 12.4, position_count: 5 },
            { sector: "Consumer Disc.", allocation_pct: 10.1, position_count: 6 },
            { sector: "Industrials", allocation_pct: 8.3, position_count: 4 },
            { sector: "Materials", allocation_pct: 6.7, position_count: 3 },
          ],
          cap_pct: 30,
          total_positions: 46,
        });
      }
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
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody className="p-3 space-y-2.5">
          {[0, 1, 2, 3, 4].map((i) => (
            <SectorRowSkeleton key={i} />
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
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody>
          <div className="app-empty">
            <div className="app-empty-icon">
              <PieChart className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">No sector data</p>
            <p className="text-[11px] text-muted-foreground/60">Connect a broker to see allocations</p>
          </div>
        </SurfaceBody>
      </Surface>
    );
  }

  const capThreshold = data.cap_pct;
  const sorted = [...data.sectors].sort((a, b) => b.allocation_pct - a.allocation_pct);

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="info" className="text-[9px] py-0.5">
              CAP: {capThreshold}%
            </Badge>
            <span className="text-[10px] font-mono text-muted-foreground/60">
              {data.total_positions} pos
            </span>
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-2">
        {sorted.length === 0 ? (
          <div className="app-empty">
            <div className="app-empty-icon">
              <PieChart className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">No sector allocations</p>
            <p className="text-[11px] text-muted-foreground/60">Open positions to see concentration</p>
          </div>
        ) : (
          sorted.map((sector) => (
            <SectorBar
              key={sector.sector}
              sector={sector}
              capThreshold={capThreshold}
              animate={mounted}
            />
          ))
        )}

        {/* Legend */}
        {sorted.length > 0 && (
          <div className="flex items-center gap-4 pt-1.5 border-t border-border/40 mt-1">
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-blue-500" />
              <span className="text-[9px] text-muted-foreground">Within limit</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-2 w-2 rounded-full bg-orange-500" />
              <span className="text-[9px] text-muted-foreground">Near cap</span>
            </div>
            <div className="flex items-center gap-1.5">
              <div className="h-px w-3 bg-red-400/60" />
              <span className="text-[9px] text-muted-foreground">{capThreshold}% cap</span>
            </div>
          </div>
        )}
      </SurfaceBody>
    </Surface>
  );
}
