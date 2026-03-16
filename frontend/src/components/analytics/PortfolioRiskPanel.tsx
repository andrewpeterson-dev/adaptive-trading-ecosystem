"use client";

import React, { useEffect, useState, useCallback } from "react";
import { ShieldCheck, Loader2, Info } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { PortfolioAnalytics } from "@/types/portfolio-analytics";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { EmptyState } from "@/components/ui/empty-state";

const RATING_COLORS: Record<string, string> = {
  low: "text-emerald-200 bg-emerald-400/10 border-emerald-400/30",
  moderate: "text-amber-200 bg-amber-400/10 border-amber-400/30",
  high: "text-orange-200 bg-orange-400/10 border-orange-400/30",
  critical: "text-red-200 bg-red-400/10 border-red-400/30",
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
    <div className="space-y-3">
      <div className="app-skeleton mx-auto h-8 w-24 rounded-full" />
      <div className="grid grid-cols-2 gap-3">
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="space-y-1">
            <div className="app-skeleton h-3 w-16 rounded" />
            <div className="app-skeleton h-5 w-20 rounded" />
          </div>
        ))}
      </div>
      <div className="app-skeleton h-10 rounded" />
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
    <div className="app-panel p-4">
      <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium uppercase tracking-[0.18em] text-muted-foreground">
        <ShieldCheck className="h-4 w-4" />
        Portfolio Risk
      </div>

      {loading && <SkeletonBlock />}

      {!loading && error && (
        <EmptyState title="Unable to load portfolio analytics" description="Check your broker connection and try refreshing." className="py-6" />
      )}

      {!loading && !error && !data && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <Badge className={RATING_COLORS.moderate}>
              <span className="opacity-50">Moderate Risk</span>
            </Badge>
            <span className="text-[9px] font-semibold px-2 py-0.5 rounded uppercase tracking-widest bg-muted/30 text-slate-500 border border-dashed border-border/50">
              Example
            </span>
          </div>
          <div className="grid grid-cols-2 gap-3 rounded-[20px] border border-dashed border-border/50 bg-muted/10 p-4 opacity-40">
            <div className="space-y-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">VaR 95%</span>
              <div className="text-base font-mono tabular-nums font-semibold">2.14%</div>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Beta</span>
              <div className="text-base font-mono tabular-nums font-semibold">1.05</div>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">CVaR</span>
              <div className="text-base font-mono tabular-nums font-semibold">3.42%</div>
            </div>
            <div className="space-y-1">
              <span className="text-[10px] text-muted-foreground uppercase tracking-wider">Max DD</span>
              <div className="text-base font-mono tabular-nums font-semibold">8.70%</div>
            </div>
          </div>
          <p className="text-xs text-slate-400 text-center leading-relaxed">
            Risk metrics populate once you have open positions. Deploy a strategy to see VaR, Beta, CVaR, and drawdown analytics.
          </p>
        </div>
      )}

      {!loading && !error && data && (
        <>
          {/* Risk Rating Badge */}
          <div className="flex items-center justify-between">
            <Badge className={RATING_COLORS[data.risk_rating] || RATING_COLORS.moderate}>
              {(data.risk_rating || "moderate").charAt(0).toUpperCase() + (data.risk_rating || "moderate").slice(1)} Risk
            </Badge>
            <span className="text-[10px] text-muted-foreground">
              {data.positions_analyzed} positions
            </span>
          </div>

          {/* 2x2 Metrics Grid */}
          <div className="grid grid-cols-2 gap-3 rounded-[20px] border border-border/70 bg-muted/30 p-4">
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
          <div className="flex items-center justify-between rounded-[18px] border border-border/70 bg-muted/30 px-4 py-3">
            <div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Expected Shortfall (CVaR)
              </div>
              <div className="text-sm text-muted-foreground mt-0.5">
                Average loss beyond VaR 99%
              </div>
            </div>
            <div className="text-lg font-mono tabular-nums font-bold text-red-300">
              {((data.expected_shortfall ?? 0) * 100).toFixed(2)}%
            </div>
          </div>

          {/* Volatility Bar */}
          <div>
            <div className="mb-1 flex justify-between text-[10px]">
              <span className="text-muted-foreground uppercase tracking-[0.18em]">Volatility</span>
              <span className="font-mono tabular-nums">
                {((data.volatility ?? 0) * 100).toFixed(1)}%
              </span>
            </div>
            <Progress
              value={Math.min((data.volatility ?? 0) * 200, 100)}
              indicatorClassName={volBarColor(data.volatility ?? 0)}
            />
            <div className="mt-0.5 flex justify-between text-[9px] text-muted-foreground/50">
              <span>0%</span>
              <span>50%+</span>
            </div>
          </div>
        </>
      )}
      </div>
    </div>
  );
}
