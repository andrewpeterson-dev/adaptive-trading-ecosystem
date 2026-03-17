"use client";

import React, { useEffect, useState, useCallback } from "react";
import { Unplug, RefreshCw, Brain, Activity } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { ModelCard } from "@/components/analytics/ModelCard";
import { RegimeIndicator } from "@/components/analytics/RegimeIndicator";
import { AllocationChart } from "@/components/analytics/AllocationChart";
import type { ModelDetail, RegimeData, EnsembleStatus } from "@/types/models";
import type { AllocationEntry } from "@/types/portfolio";
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton, CardSkeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { useToast } from "@/components/ui/toast";
import { useTradingMode } from "@/hooks/useTradingMode";

export default function ModelsPage() {
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [ensemble, setEnsemble] = useState<EnsembleStatus | null>(null);
  const [allocation, setAllocation] = useState<AllocationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const { toast } = useToast();
  const { mode } = useTradingMode();

  const fetchAll = useCallback(async () => {
    try {
      setError(false);
      const [modRes, regRes, ensembleRes, allocRes] = await Promise.allSettled([
        apiFetch<{ models: ModelDetail[] }>("/api/models/list"),
        apiFetch<RegimeData>("/api/models/regime"),
        apiFetch<EnsembleStatus>("/api/models/ensemble-status"),
        apiFetch<{ allocations: AllocationEntry[] }>("/api/models/allocation"),
      ]);

      let hasData = false;

      if (modRes.status === "fulfilled") {
        const data = modRes.value;
        const list = data.models ?? [];
        setModels(list);
        hasData = true;
      } else {
        setModels([]);
      }

      if (regRes.status === "fulfilled") {
        const regimeData = regRes.value;
        setRegime(regimeData?.status === "no_data" || !regimeData?.regime ? null : regimeData);
        hasData = true;
      } else {
        setRegime(null);
      }

      if (ensembleRes.status === "fulfilled") {
        setEnsemble(ensembleRes.value);
        hasData = true;
      } else {
        setEnsemble(null);
      }

      if (allocRes.status === "fulfilled") {
        const data = allocRes.value;
        setAllocation(data.allocations ?? []);
        hasData = true;
      } else {
        setAllocation([]);
      }

      setError(!hasData);
      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    setLoading(true);
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRetrain = async (modelName: string) => {
    try {
      const result = await apiFetch<{ message?: string }>(
        `/api/models/retrain?model_name=${encodeURIComponent(modelName)}`,
        { method: "POST", maxRetries: 0 }
      );
      toast(result.message || `Retraining queued for ${modelName}`, "success");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "Failed to queue retraining";
      toast(`Failed to queue retraining for ${modelName}: ${message}`, "error");
      throw err;
    }
  };

  const ensembleWeightCount = ensemble ? Object.keys(ensemble.weights ?? {}).length : 0;
  const retrainingSupported = ensemble?.retraining_supported === true;

  const renderContent = () => {
    if (loading) {
      return (
        <div className="space-y-4">
          <div className="app-panel p-5 space-y-3">
            <Skeleton className="h-5 w-40" />
            <Skeleton className="h-3 w-72" />
          </div>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <CardSkeleton />
            <CardSkeleton />
          </div>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
            <CardSkeleton />
            <CardSkeleton />
            <CardSkeleton />
          </div>
          <div className="app-panel p-5 space-y-3">
            <Skeleton className="h-4 w-32" />
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-4 py-2">
                <Skeleton className="h-4 w-24" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-16" />
                <Skeleton className="h-4 w-16" />
              </div>
            ))}
          </div>
        </div>
      );
    }
    if (error && models.length === 0) {
      return (
        <EmptyState
          icon={<Unplug className="h-5 w-5 text-muted-foreground" />}
          title="No model data available"
          description="Regime detection and allocation recommendations will populate after the AI models have sufficient market data to analyze. Ensure the backend is running and models are trained."
        />
      );
    }
    return null;
  };

  const earlyContent = renderContent();

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/ai-intelligence", label: "Market Intel" },
        { href: "/models", label: "Models" },
        { href: "/quant", label: "Quant" },
      ]} />

      {earlyContent ? earlyContent : (
      <>
      <PageHeader
        eyebrow="Signals"
        title="Model Performance"
        description="Audit active models, inspect ensemble balance, and compare predictive systems side by side with consistent capital and regime context."
        meta={
          <>
            <Badge variant={mode === "live" ? "positive" : "info"} className="tracking-normal">
              {mode === "live" ? "Live mode" : "Paper mode"}
            </Badge>
            <Badge variant="neutral" className="tracking-normal">
              <span className="font-mono">{models.length}</span>
              models
            </Badge>
            {ensembleWeightCount > 0 && (
              <Badge variant="info" className="tracking-normal">
                <span className="font-mono">{ensembleWeightCount}</span>
                in ensemble
              </Badge>
            )}
            {lastRefresh && (
              <Badge variant="neutral" className="tracking-normal font-mono">
                Updated {lastRefresh.toLocaleTimeString()}
              </Badge>
            )}
          </>
        }
        actions={
          <Button onClick={fetchAll} variant="secondary" size="sm">
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.9fr)]">
        {regime ? (
          <RegimeIndicator data={regime} />
        ) : (
          <div className="app-panel p-5 space-y-3">
            <div className="flex items-center justify-between">
              <div className="app-section-title flex items-center gap-2 mb-0">
                <Activity className="h-4 w-4" />
                Regime Detection
              </div>
              <span className="text-[9px] font-semibold px-2 py-0.5 rounded uppercase tracking-widest bg-muted/30 text-slate-500 border border-dashed border-border/50">
                Preview
              </span>
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Regime detection and allocation recommendations will populate after the AI models have sufficient market data to analyze.
            </p>
            <div className="grid grid-cols-3 gap-2 opacity-30 pointer-events-none">
              {["Bull Trend", "Mean Reversion", "High Volatility"].map((label) => (
                <div key={label} className="rounded-xl border border-dashed border-border/50 bg-muted/10 p-3 text-center">
                  <div className="text-xs font-medium text-foreground">{label}</div>
                  <div className="mt-1 text-[10px] font-mono text-muted-foreground">--</div>
                </div>
              ))}
            </div>
          </div>
        )}

        <div className="app-panel p-5">
          <div className="app-section-title flex items-center gap-2">
            <Brain className="h-4 w-4" />
            Ensemble Allocation
          </div>
          {ensemble && ensemble.model_count > 0 ? (
            <div className="mt-4 space-y-3">
              {Object.entries(ensemble.weights ?? {}).map(([name, weight]) => (
                <div key={name} className="app-inset p-3">
                  <div className="flex items-center justify-between gap-3 text-sm">
                    <span className="text-foreground">{name}</span>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {(weight * 100).toFixed(1)}%
                    </span>
                  </div>
                  <div className="app-progress-track mt-3">
                    <div
                      className="app-progress-bar bg-primary"
                      style={{ width: `${Math.min(weight * 100, 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-4 space-y-3">
              <p className="text-sm text-slate-400 leading-relaxed">
                Ensemble allocation weights appear here once models are trained and contributing predictions.
              </p>
              <div className="space-y-3 opacity-30 pointer-events-none">
                {[
                  { name: "Momentum Model", weight: 0.40 },
                  { name: "Mean Reversion", weight: 0.35 },
                  { name: "Volatility Adj.", weight: 0.25 },
                ].map((m) => (
                  <div key={m.name} className="app-inset p-3 border border-dashed border-border/40">
                    <div className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-foreground">{m.name}</span>
                      <span className="font-mono text-xs tabular-nums text-muted-foreground">
                        {(m.weight * 100).toFixed(1)}%
                      </span>
                    </div>
                    <div className="app-progress-track mt-3">
                      <div className="app-progress-bar bg-primary" style={{ width: `${m.weight * 100}%` }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      {models.length > 0 && (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2 2xl:grid-cols-3">
          {models.map((model) => (
            <ModelCard
              key={model.name}
              model={model}
              onRetrain={handleRetrain}
              retrainAvailable={retrainingSupported}
            />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-[minmax(320px,0.8fr)_minmax(0,1.2fr)]">
        {allocation.length > 0 ? (
          <AllocationChart data={allocation} />
        ) : (
          <div className="app-panel p-5 space-y-3">
            <div className="app-section-title flex items-center gap-2">
              <Brain className="h-4 w-4" />
              Capital Allocation
            </div>
            <p className="text-sm text-slate-400 leading-relaxed">
              Capital allocation appears here after portfolio weights are calculated from model outputs and risk constraints.
            </p>
            <div className="rounded-xl border border-dashed border-border/50 bg-muted/10 p-4 opacity-30 pointer-events-none">
              <div className="flex items-center justify-center h-24 text-sm text-muted-foreground">
                Allocation chart preview
              </div>
            </div>
          </div>
        )}

        <div className="app-table-shell overflow-x-auto">
          <div className="app-section-header">
            <div>
              <h3 className="text-sm font-semibold">Model Comparison</h3>
              <p className="mt-0.5 text-xs text-muted-foreground">
                High-level ranking metrics across the active model inventory.
              </p>
            </div>
          </div>
          {models.length === 0 ? (
            <EmptyState
              title="No models registered"
              description="Train your first model to see Sharpe ratios, win rates, drawdowns, and return metrics compared side by side."
              className="py-12"
            />
          ) : (
            <table className="app-table">
              <thead>
                <tr>
                  <th>Model</th>
                  <th>Type</th>
                  <th>Active</th>
                  <th>Sharpe</th>
                  <th>Sortino</th>
                  <th>Win Rate</th>
                  <th>Max DD</th>
                  <th>Return</th>
                  <th>Trades</th>
                </tr>
              </thead>
              <tbody>
                {models.map((model) => (
                  <tr key={model.name}>
                    <td className="font-medium">{model.name}</td>
                    <td className="text-xs uppercase tracking-[0.12em] text-muted-foreground">
                      {model.model_type.replace("Model", "")}
                    </td>
                    <td>
                      <span
                        className={`inline-flex h-2.5 w-2.5 rounded-full ${
                          model.is_active ? "bg-emerald-400" : "bg-muted-foreground/35"
                        }`}
                      />
                    </td>
                    <td className="font-mono tabular-nums">
                      {model.sharpe_ratio != null ? model.sharpe_ratio.toFixed(3) : "—"}
                    </td>
                    <td className="font-mono tabular-nums">
                      {model.sortino_ratio != null ? model.sortino_ratio.toFixed(3) : "—"}
                    </td>
                    <td className="font-mono tabular-nums">
                      {model.win_rate != null ? `${(model.win_rate * 100).toFixed(1)}%` : "—"}
                    </td>
                    <td className="font-mono tabular-nums">
                      {model.max_drawdown != null
                        ? `${(model.max_drawdown * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="font-mono tabular-nums">
                      {model.total_return != null
                        ? `${(model.total_return * 100).toFixed(1)}%`
                        : "—"}
                    </td>
                    <td className="font-mono tabular-nums text-muted-foreground">
                      {model.num_trades}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
      </>
      )}
    </div>
  );
}
