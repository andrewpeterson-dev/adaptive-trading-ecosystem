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
import { HoldingsTable } from "@/components/analytics/HoldingsTable";
import { PortfolioOptimizer } from "@/components/analytics/PortfolioOptimizer";
import type { ModelInfo, AllocationEntry, EquityCurvePoint } from "@/types/portfolio";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

function MetricCell({ value, format }: { value: number | null; format?: string }) {
  if (value === null || value === undefined)
    return <span className="text-muted-foreground/50">—</span>;
  if (format === "percent") {
    return (
      <span className={value > 0 ? "text-emerald-400" : value < 0 ? "text-red-400" : ""}>
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

  /**
   * Tickers surfaced by HoldingsTable → pre-fills PortfolioOptimizer.
   * Starts empty; populated once live positions load.
   */
  const [holdingTickers, setHoldingTickers] = useState<string>("");

  const fetchAll = useCallback(async () => {
    try {
      setError(false);
      const q = `?mode=${mode}`;
      const [eqRes, allocRes, modRes, regRes] = await Promise.allSettled([
        apiFetch<any>(`/api/dashboard/equity-curve${q}`),
        apiFetch<any>(`/api/models/allocation${q}`),
        apiFetch<any>(`/api/models/list${q}`),
        apiFetch<any>(`/api/models/regime${q}`),
      ]);

      let hasData = false;

      if (eqRes.status === "fulfilled") {
        const data = eqRes.value;
        const rawPoints: any[] = data.equity_curve || (Array.isArray(data) ? data : []);
        // Normalize: API returns {date, equity} but EquityCurveChart expects {date, value}
        setEquityCurve(rawPoints.map((p: any) => ({
          date: p.date,
          value: p.value ?? p.equity ?? 0,
        })));
        hasData = true;
      }

      if (allocRes.status === "fulfilled") {
        const data = allocRes.value;
        const raw = data?.allocations ?? data;
        setAllocation(Array.isArray(raw) ? raw : []);
        hasData = true;
      }

      if (modRes.status === "fulfilled") {
        const data = modRes.value;
        const raw = Array.isArray(data) ? data : (data?.models ?? []);
        setModels(Array.isArray(raw) ? raw : []);
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

  const renderEarlyContent = () => {
    if (loading) {
      return (
        <div className="space-y-4">
          <div className="h-[300px] animate-pulse rounded-2xl bg-muted/20" />
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="h-48 animate-pulse rounded-2xl bg-muted/20" />
            <div className="h-48 animate-pulse rounded-2xl bg-muted/20" />
          </div>
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

  const earlyContent = renderEarlyContent();
  const regimeLabel =
    regime?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ?? "Unknown";

  return (
    <div className="app-page">
      <SubNav
        items={[
          { href: "/dashboard", label: "Overview" },
          { href: "/portfolio", label: "Portfolio" },
          { href: "/risk", label: "Risk" },
        ]}
      />

      {earlyContent ? (
        earlyContent
      ) : (
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

          {/* ── Equity Curve ─────────────────────────────────────────────── */}
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

          {/* ── Allocation + Model Performance ───────────────────────────── */}
          <div className="grid grid-cols-1 gap-5 lg:grid-cols-3">
            {allocation.length > 0 && <AllocationChart data={allocation} />}

            <div
              className={`app-table-shell ${
                allocation.length > 0 ? "lg:col-span-2" : "lg:col-span-3"
              }`}
            >
              <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
                <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
                  Model Performance
                </div>
              </div>
              {models.length === 0 ? (
                <EmptyState
                  icon={<Layers className="h-5 w-5 text-muted-foreground/70" />}
                  title="No active models"
                  description="Deploy a strategy from the Strategy Builder to populate model performance metrics here. Sharpe ratios, win rates, max drawdowns, and total returns will appear as strategies execute trades."
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
                          <td className="text-xs text-muted-foreground uppercase tracking-wide">
                            {m.model_type}
                          </td>
                          <td>
                            <span
                              className={`inline-flex items-center gap-1 text-xs font-medium ${
                                m.is_active
                                  ? "text-emerald-300"
                                  : "text-muted-foreground/50"
                              }`}
                            >
                              <span
                                className={`h-1.5 w-1.5 rounded-full ${
                                  m.is_active ? "bg-emerald-300" : "bg-muted-foreground/30"
                                }`}
                              />
                              {m.is_active ? "On" : "Off"}
                            </span>
                          </td>
                          <td className="font-mono text-sm tabular-nums">
                            <MetricCell value={m.sharpe_ratio} format="ratio" />
                          </td>
                          <td className="font-mono text-sm tabular-nums">
                            <MetricCell value={m.win_rate} format="percent" />
                          </td>
                          <td className="font-mono text-sm tabular-nums">
                            <MetricCell value={m.max_drawdown} format="percent" />
                          </td>
                          <td className="font-mono text-sm tabular-nums">
                            <MetricCell value={m.total_return} format="percent" />
                          </td>
                          <td className="font-mono text-sm tabular-nums text-muted-foreground">
                            {m.num_trades}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>

          {/* ── Current Holdings ─────────────────────────────────────────── */}
          {/*
           * Endpoint: GET /api/webull/positions
           * Fetches live broker positions → shows holdings table + donut chart.
           * onTickersReady pipes the loaded tickers into the optimizer below.
           */}
          <HoldingsTable
            onTickersReady={(tickers) => setHoldingTickers(tickers.join(","))}
          />

          {/* ── Portfolio Optimizer ───────────────────────────────────────── */}
          {/*
           * Endpoints:
           *   POST /api/portfolio/optimize              — standard methods
           *   POST /api/portfolio/optimize/black-litterman — BL method
           *   GET  /api/portfolio/efficient-frontier    — frontier chart
           *   GET  /api/portfolio/rebalance-plan        — live → proposed trades
           * TODO: POST /api/trading/execute-rebalance   — execute orders (not yet implemented)
           */}
          <PortfolioOptimizer
            initialTickers={holdingTickers || "SPY,QQQ,IWM,TLT,GLD,VNQ"}
          />
        </>
      )}
    </div>
  );
}
