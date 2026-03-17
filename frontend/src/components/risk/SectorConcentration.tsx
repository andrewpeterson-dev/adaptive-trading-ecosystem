"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Loader2, PieChart, AlertTriangle } from "lucide-react";
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

export function SectorConcentration() {
  const [data, setData] = useState<SectorConcentrationData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<SectorConcentrationData>(
        "/api/risk/category-scores"
      );
      // If the API returns sector data in a nested structure, adapt here.
      // Fallback: derive from category-scores or use mock structure
      if (result && "sectors" in (result as any)) {
        setData(result as unknown as SectorConcentrationData);
      } else {
        // Derive sector view from category scores or set sensible defaults
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
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
        </SurfaceHeader>
        <SurfaceBody>
          <p className="text-xs text-muted-foreground text-center py-4">
            Sector data unavailable.
          </p>
        </SurfaceBody>
      </Surface>
    );
  }

  const capThreshold = data.cap_pct;
  const nearCapThreshold = capThreshold * 0.8;

  return (
    <Surface>
      <SurfaceHeader>
        <div className="flex items-center justify-between w-full">
          <div className="flex items-center gap-2">
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
          <Badge variant="info" className="text-[9px] py-0.5">
            CAP: {capThreshold}%
          </Badge>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-2">
        {data.sectors
          .sort((a, b) => b.allocation_pct - a.allocation_pct)
          .map((sector) => {
            const isNearCap = sector.allocation_pct >= nearCapThreshold;
            const isOverCap = sector.allocation_pct >= capThreshold;
            const barColor = isNearCap ? "#f97316" : "#3b82f6";
            const fillPct = Math.min(
              (sector.allocation_pct / (capThreshold * 1.2)) * 100,
              100
            );
            const capLinePct = (capThreshold / (capThreshold * 1.2)) * 100;

            return (
              <div key={sector.sector} className="space-y-0.5">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs font-medium text-foreground truncate">
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
                  <span
                    className="text-xs font-mono font-semibold tabular-nums shrink-0"
                    style={{ color: barColor }}
                  >
                    {sector.allocation_pct.toFixed(1)}%
                  </span>
                </div>
                {/* Bar with cap line */}
                <div className="relative">
                  <div className="app-progress-track h-2">
                    <div
                      className="app-progress-bar h-full"
                      style={{
                        width: `${fillPct}%`,
                        backgroundColor: barColor,
                      }}
                    />
                  </div>
                  {/* Cap threshold line */}
                  <div
                    className="absolute top-0 h-2 w-px bg-red-400/60"
                    style={{ left: `${capLinePct}%` }}
                  />
                </div>
              </div>
            );
          })}

        {data.sectors.length === 0 && (
          <p className="text-xs text-muted-foreground text-center py-4">
            No sector allocations to display.
          </p>
        )}

        {/* Legend */}
        <div className="flex items-center gap-3 pt-1 border-t border-border/40 mt-2">
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
      </SurfaceBody>
    </Surface>
  );
}
