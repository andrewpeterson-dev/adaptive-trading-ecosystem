"use client";

import React, { useEffect, useState, useCallback } from "react";
import { PieChart, AlertTriangle, Info } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Surface,
  SurfaceBody,
  SurfaceHeader,
  SurfaceTitle,
} from "@/components/ui/surface";

interface Position {
  ticker?: string;
  symbol?: string;
  quantity?: number;
  market_value?: number;
}

interface SectorAllocation {
  sector: string;
  allocation_pct: number;
  position_count: number;
}

// Simple ticker-to-sector map for client-side computation
const TICKER_SECTOR_MAP: Record<string, string> = {
  AAPL: "Technology", MSFT: "Technology", GOOG: "Technology", GOOGL: "Technology",
  META: "Technology", NVDA: "Technology", AMD: "Technology", INTC: "Technology",
  TSLA: "Consumer Disc.", AMZN: "Consumer Disc.", HD: "Consumer Disc.", NKE: "Consumer Disc.",
  JPM: "Financials", BAC: "Financials", GS: "Financials", MS: "Financials", V: "Financials",
  JNJ: "Healthcare", UNH: "Healthcare", PFE: "Healthcare", ABBV: "Healthcare", MRK: "Healthcare",
  XOM: "Energy", CVX: "Energy", COP: "Energy", SLB: "Energy",
  CAT: "Industrials", UPS: "Industrials", BA: "Industrials", GE: "Industrials",
  PG: "Consumer Staples", KO: "Consumer Staples", PEP: "Consumer Staples", WMT: "Consumer Staples",
  T: "Communication", VZ: "Communication", DIS: "Communication", NFLX: "Communication",
  NEE: "Utilities", DUK: "Utilities", SO: "Utilities",
  AMT: "Real Estate", PLD: "Real Estate", SPG: "Real Estate",
  LIN: "Materials", APD: "Materials", FCX: "Materials",
  SPY: "ETF", QQQ: "ETF", IWM: "ETF", DIA: "ETF",
};

const DEFAULT_CAP_PCT = 30;

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

/** Compute sector allocations client-side from position data. */
function computeSectorAllocations(positions: Position[]): SectorAllocation[] {
  const sectorMap = new Map<string, { totalValue: number; count: number }>();
  let totalPortfolioValue = 0;

  for (const pos of positions) {
    const ticker = pos.ticker || pos.symbol || "";
    const value = pos.market_value ?? 0;
    const sector = TICKER_SECTOR_MAP[ticker.toUpperCase()] || "Other";
    totalPortfolioValue += value;

    const existing = sectorMap.get(sector) || { totalValue: 0, count: 0 };
    existing.totalValue += value;
    existing.count += 1;
    sectorMap.set(sector, existing);
  }

  if (totalPortfolioValue === 0) return [];

  const allocations: SectorAllocation[] = [];
  for (const [sector, data] of Array.from(sectorMap.entries())) {
    allocations.push({
      sector,
      allocation_pct: (data.totalValue / totalPortfolioValue) * 100,
      position_count: data.count,
    });
  }

  return allocations.sort((a, b) => b.allocation_pct - a.allocation_pct);
}

export function SectorConcentration() {
  const [sectors, setSectors] = useState<SectorAllocation[]>([]);
  const [loading, setLoading] = useState(true);
  const [hasPositions, setHasPositions] = useState(false);
  const [mounted, setMounted] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const result = await apiFetch<{ positions?: Position[]; holdings?: Position[] }>(
        "/api/trading/positions"
      );
      const positions = result?.positions || result?.holdings || [];
      if (positions.length > 0) {
        setHasPositions(true);
        setSectors(computeSectorAllocations(positions));
      } else {
        setHasPositions(false);
        setSectors([]);
      }
    } catch {
      setHasPositions(false);
      setSectors([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  useEffect(() => {
    if (!loading && sectors.length > 0) {
      const raf = requestAnimationFrame(() => setMounted(true));
      return () => cancelAnimationFrame(raf);
    }
  }, [loading, sectors]);

  const capThreshold = DEFAULT_CAP_PCT;

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

  if (!hasPositions || sectors.length === 0) {
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
        <SurfaceBody>
          <div className="app-empty">
            <div className="app-empty-icon">
              <Info className="h-5 w-5 text-muted-foreground/60" />
            </div>
            <p className="text-xs font-medium text-muted-foreground">Sector tracking requires broker positions data</p>
            <p className="text-[11px] text-muted-foreground/60">Connect a broker and open positions to see concentration</p>
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
            <PieChart className="h-4 w-4 text-muted-foreground" />
            <SurfaceTitle>Sector Concentration</SurfaceTitle>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant="info" className="text-[9px] py-0.5">
              CAP: {capThreshold}%
            </Badge>
            <span className="text-[10px] font-mono text-muted-foreground/60">
              {sectors.reduce((sum, s) => sum + s.position_count, 0)} pos
            </span>
          </div>
        </div>
      </SurfaceHeader>
      <SurfaceBody className="p-3 space-y-2">
        {sectors.map((sector) => (
          <SectorBar
            key={sector.sector}
            sector={sector}
            capThreshold={capThreshold}
            animate={mounted}
          />
        ))}

        {/* Legend */}
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
      </SurfaceBody>
    </Surface>
  );
}
