"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  TrendingUp,
  Layers,
  Activity,
  Unplug,
  RefreshCw,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import { AllocationChart } from "@/components/analytics/AllocationChart";
import type { ModelInfo, AllocationEntry, EquityCurvePoint } from "@/types/portfolio";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";
import { PortfolioOptimizer } from "@/components/analytics/PortfolioOptimizer";

function MetricCell({ value, format }: { value: number | null; format?: string }) {
  if (value === null || value === undefined) return <span className="text-muted-foreground/50">—</span>;
  if (format === "percent") {
    const isPositive = value >= 0;
    return (
      <span className={format === "percent" && (value > 0) ? "text-emerald-400" : format === "percent" && value < 0 ? "text-red-400" : ""}>
        {(value * 100).toFixed(1)}%
      </span>
    );
  }
  if (format === "ratio") return <span>{value.toFixed(3)}</span>;
  return <span>{value}</span>;
}

export default function PortfolioPage() {
  const [equityCurve, setEquityCurve] = useState<EquityCurvePoint[]>([]);
  const [allocation, setAllocation] = useState<AllocationEntry[]>([]);
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [regime, setRegime] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const { mode } = useTradingMode();

  const fetchAll = useCallback(async () => {
    try {
      const q = `?mode=${mode}`;
      const [eqRes, allocRes, modRes, regRes] = await Promise.allSettled([
        apiFetch<any>(`/api/dashboard/equity-curve${q}`),
        apiFetch<any>("/api/models/allocation"),
        apiFetch<any>("/api/models/list"),
        apiFetch<any>("/api/models/regime"),
      ]);

      let hasData = false;

      if (eqRes.status === "fulfilled") {
        const data = eqRes.value;
        setEquityCurve(data.equity_curve || data || []);
        hasData = true;
      }

      if (allocRes.status === "fulfilled") {
        const data = allocRes.value;
        setAllocation(data.allocations || data || []);
        hasData = true;
      }

      if (modRes.status === "fulfilled") {
        const data = modRes.value;
        setModels(Array.isArray(data) ? data : data.models || []);
        hasData = true;
      }

      if (regRes.status === "fulfilled") {
        const data = regRes.value;
        setRegime(data.regime || data.current_regime || null);
        hasData = true;
      }

      if (!hasData) setError(true);
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, [mode]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-32">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      );
    }
    if (error && !models.length && !equityCurve.length) {
      return (
        <div className="app-panel">
          <EmptyState
            icon={<Unplug className="h-5 w-5 text-muted-foreground/70" />}
            title="Portfolio analytics are unavailable"
            description="Your equity curve, capital allocation chart, and model performance table will populate here once you connect a broker and deploy strategies. Start by building a strategy and running it in paper mode."
          />
        </div>
      );
    }
    return null;
  };

  const earlyContent = renderContent();
  const regimeLabel = regime?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Unknown";

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/dashboard", label: "Overview" },
        { href: "/portfolio", label: "Portfolio" },
        { href: "/risk", label: "Risk" },
      ]} />

      {earlyContent ? earlyContent : (
      <>
      <PageHeader
        eyebrow="Capital"
        title="Portfolio"
        description="Review deployed models, capital allocation, and regime posture in one polished analytics view."
        badge={
          <Badge variant={mode === "live" ? "negative" : "info"}>
            {mode === "live" ? "Live" : "Paper"}
          </Badge>
        }
        meta={
          <>
            <Badge className="font-mono tracking-normal">
              {models.length} model{models.length !== 1 ? "s" : ""} deployed
            </Badge>
            {regime && (
              <Badge>
                <Activity className="h-3.5 w-3.5" />
                {regimeLabel}
              </Badge>
            )}
          </>
        }
        actions={
          <Button variant="secondary" size="sm" onClick={fetchAll}>
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      {equityCurve.length > 0 && (
        <div className="app-panel overflow-hidden">
          <div className="px-4 py-3 border-b border-border/50">
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
              <TrendingUp className="h-3.5 w-3.5" />
              Equity Curve
            </div>
          </div>
          <div className="p-4">
            <EquityCurveChart data={equityCurve} height={280} />
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
        {allocation.length > 0 && <AllocationChart data={allocation} />}

        <div className={`app-table-shell ${allocation.length > 0 ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
              Model Performance
            </div>
          </div>
          {models.length === 0 ? (
            <EmptyState
              icon={<Layers className="h-5 w-5 text-muted-foreground/70" />}
              title="No models trained yet"
              description="Once you train a model, this table will show Sharpe ratios, win rates, max drawdowns, and total returns for each active model in your portfolio."
              className="py-12"
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Model</th>
                    <th>Type</th>
                    <th>Active</th>
                    <th>Sharpe</th>
                    <th>Win Rate</th>
                    <th>Max DD</th>
                    <th>Return</th>
                    <th>Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m) => (
                    <tr key={m.name}>
                      <td className="font-medium text-sm">{m.name}</td>
                      <td className="text-xs text-muted-foreground uppercase tracking-wide">{m.model_type}</td>
                      <td>
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${m.is_active ? "text-emerald-300" : "text-muted-foreground/50"}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${m.is_active ? "bg-emerald-300" : "bg-muted-foreground/30"}`} />
                          {m.is_active ? "On" : "Off"}
                        </span>
                      </td>
                      <td className="font-mono text-sm tabular-nums"><MetricCell value={m.sharpe_ratio} format="ratio" /></td>
                      <td className="font-mono text-sm tabular-nums"><MetricCell value={m.win_rate} format="percent" /></td>
                      <td className="font-mono text-sm tabular-nums"><MetricCell value={m.max_drawdown} format="percent" /></td>
                      <td className="font-mono text-sm tabular-nums"><MetricCell value={m.total_return} format="percent" /></td>
                      <td className="font-mono text-sm tabular-nums text-muted-foreground">{m.num_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>

      {/* Portfolio Optimization Section */}
      <PortfolioOptimizer />
      </>
      )}
    </div>
  );
}
