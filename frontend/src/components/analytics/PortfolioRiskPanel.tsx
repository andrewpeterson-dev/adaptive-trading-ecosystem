"use client";

import React, { useEffect, useState, useCallback } from "react";
import { ShieldCheck, Loader2, Info } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { PortfolioAnalytics } from "@/types/portfolio-analytics";

const RATING_COLORS: Record<string, string> = {
  low: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
  moderate: "text-amber-400 bg-amber-400/10 border-amber-400/30",
  high: "text-orange-400 bg-orange-400/10 border-orange-400/30",
  critical: "text-red-400 bg-red-400/10 border-red-400/30",
};

function volBarColor(vol: number): string {
  if (vol < 0.15) return "bg-emerald-500";
  if (vol < 0.25) return "bg-amber-500";
  return "bg-red-500";
}

interface MetricProps {
  label: string;
  value: string;
  tooltip: string;
}

function MetricCell({ label, value, tooltip }: MetricProps) {
  const [showTip, setShowTip] = useState(false);
  return (
    <div className="relative space-y-1">
      <div className="flex items-center gap-1">
        <span className="text-[10px] text-muted-foreground uppercase tracking-wider">{label}</span>
        <button
          className="text-muted-foreground/50 hover:text-muted-foreground transition-colors"
          onMouseEnter={() => setShowTip(true)}
          onMouseLeave={() => setShowTip(false)}
          onClick={() => setShowTip((p) => !p)}
          type="button"
        >
          <Info className="h-3 w-3" />
        </button>
        {showTip && (
          <div className="absolute left-0 bottom-full mb-1 z-10 px-2 py-1 rounded bg-popover border border-border text-[10px] text-muted-foreground max-w-[200px] shadow-lg">
            {tooltip}
          </div>
        )}
      </div>
      <div className="text-base font-mono tabular-nums font-semibold">{value}</div>
    </div>
  );
}

function SkeletonBlock() {
  return (
    <div className="space-y-3 animate-pulse">
      <div className="h-8 w-24 rounded-full bg-muted mx-auto" />
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-1">
            <div className="h-3 w-16 bg-muted rounded" />
            <div className="h-5 w-20 bg-muted rounded" />
          </div>
        ))}
      </div>
      <div className="h-10 bg-muted rounded" />
    </div>
  );
}

export function PortfolioRiskPanel() {
  const [data, setData] = useState<PortfolioAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await apiFetch<PortfolioAnalytics>("/api/trading/portfolio-analytics");
      setData(data);
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

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-4">
      <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
        <ShieldCheck className="h-4 w-4" />
        Portfolio Risk
      </div>

      {loading && <SkeletonBlock />}

      {!loading && error && (
        <div className="py-6 text-center text-muted-foreground text-sm">
          Unable to load portfolio analytics
        </div>
      )}

      {!loading && !error && !data && (
        <div className="py-6 text-center text-muted-foreground text-sm">
          No analytics data available
        </div>
      )}

      {!loading && !error && data && (
        <>
          {/* Risk Rating Badge */}
          <div className="flex items-center justify-between">
            <span
              className={`text-sm font-semibold px-4 py-1.5 rounded-full border ${
                RATING_COLORS[data.risk_rating] || RATING_COLORS.moderate
              }`}
            >
              {(data.risk_rating || "moderate").charAt(0).toUpperCase() + (data.risk_rating || "moderate").slice(1)} Risk
            </span>
            <span className="text-[10px] text-muted-foreground">
              {data.positions_analyzed} positions
            </span>
          </div>

          {/* 2x2 Metrics Grid */}
          <div className="grid grid-cols-2 gap-3">
            <MetricCell
              label="VaR 95%"
              value={`${((data.var_95 ?? 0) * 100).toFixed(2)}%`}
              tooltip="Value at Risk: 95% confidence that daily losses will not exceed this amount"
            />
            <MetricCell
              label="VaR 99%"
              value={`${((data.var_99 ?? 0) * 100).toFixed(2)}%`}
              tooltip="Value at Risk: 99% confidence that daily losses will not exceed this amount"
            />
            <MetricCell
              label="Beta"
              value={(data.beta ?? 0).toFixed(2)}
              tooltip="Portfolio sensitivity to market movements. 1.0 = moves with market"
            />
            <MetricCell
              label="Concentration"
              value={(data.concentration_hhi ?? 0).toFixed(3)}
              tooltip="Herfindahl-Hirschman Index. Lower = more diversified. >0.25 = concentrated"
            />
          </div>

          {/* Expected Shortfall */}
          <div className="rounded-md bg-muted/30 px-3 py-2 flex items-center justify-between">
            <div>
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                Expected Shortfall (CVaR)
              </div>
              <div className="text-sm text-muted-foreground mt-0.5">
                Average loss beyond VaR 99%
              </div>
            </div>
            <div className="text-lg font-mono tabular-nums font-bold text-red-400">
              {((data.expected_shortfall ?? 0) * 100).toFixed(2)}%
            </div>
          </div>

          {/* Volatility Bar */}
          <div>
            <div className="flex justify-between text-[10px] mb-1">
              <span className="text-muted-foreground uppercase tracking-wider">Volatility</span>
              <span className="font-mono tabular-nums">
                {((data.volatility ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted overflow-hidden">
              <div
                className={`h-full rounded-full transition-all ${volBarColor(data.volatility ?? 0)}`}
                style={{ width: `${Math.min((data.volatility ?? 0) * 200, 100)}%` }}
              />
            </div>
            <div className="flex justify-between text-[9px] text-muted-foreground/50 mt-0.5">
              <span>0%</span>
              <span>50%+</span>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
