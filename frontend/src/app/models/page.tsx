"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  Unplug,
  RefreshCw,
  Brain,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { ModelCard } from "@/components/analytics/ModelCard";
import { RegimeIndicator } from "@/components/analytics/RegimeIndicator";
import { AllocationChart } from "@/components/analytics/AllocationChart";
import type { ModelDetail, RegimeData, EnsembleStatus } from "@/types/models";
import type { AllocationEntry } from "@/types/portfolio";

export default function ModelsPage() {
  const [models, setModels] = useState<ModelDetail[]>([]);
  const [regime, setRegime] = useState<RegimeData | null>(null);
  const [ensemble, setEnsemble] = useState<EnsembleStatus | null>(null);
  const [allocation, setAllocation] = useState<AllocationEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchAll = useCallback(async () => {
    try {
      const [modRes, regRes, ensRes, allocRes] = await Promise.allSettled([
        apiFetch<any>("/api/models/list"),
        apiFetch<any>("/api/models/regime"),
        apiFetch<any>("/api/models/ensemble-status"),
        apiFetch<any>("/api/models/allocation"),
      ]);

      let hasData = false;

      if (modRes.status === "fulfilled") {
        const data = modRes.value;
        setModels(data.models || data || []);
        hasData = true;
      }

      if (regRes.status === "fulfilled") {
        setRegime(regRes.value);
        hasData = true;
      }

      if (ensRes.status === "fulfilled") {
        setEnsemble(ensRes.value);
        hasData = true;
      }

      if (allocRes.status === "fulfilled") {
        const data = allocRes.value;
        setAllocation(data.allocations || data || []);
        hasData = true;
      }

      if (!hasData) setError(true);
      setLastRefresh(new Date());
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, 30000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const handleRetrain = async (modelName: string) => {
    try {
      await apiFetch("/api/models/retrain", {
        method: "POST",
        body: JSON.stringify({ model_name: modelName }),
      });
      await fetchAll();
    } catch {
      // Silently fail — user sees button reset
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && models.length === 0) {
    return (
      <div className="text-center py-20 space-y-3">
        <Unplug className="h-10 w-10 text-muted-foreground/40 mx-auto" />
        <h2 className="text-lg font-semibold">No Model Data</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Train models and start the backend to view model performance, regime detection, and capital allocation.
        </p>
      </div>
    );
  }

  const ensembleWeightCount = ensemble ? Object.keys(ensemble.weights).length : 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Model Performance</h2>
          {lastRefresh && (
            <p className="text-xs text-muted-foreground mt-0.5">
              {models.length} model{models.length !== 1 ? "s" : ""} registered
              {ensembleWeightCount > 0 && ` \u00B7 ${ensembleWeightCount} in ensemble`}
              {" \u00B7 "}Updated {lastRefresh.toLocaleTimeString()}
            </p>
          )}
        </div>
        <button
          onClick={fetchAll}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Refresh
        </button>
      </div>

      {/* Top: Regime + Ensemble Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <RegimeIndicator data={regime} />

        {ensemble && (
          <div className="rounded-lg border border-border/50 bg-card p-4 space-y-3">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider">
              <Brain className="h-4 w-4" />
              Ensemble Weights
            </div>
            <div className="space-y-2">
              {Object.entries(ensemble.weights).map(([name, weight]) => (
                <div key={name} className="flex items-center justify-between text-sm">
                  <span className="text-muted-foreground">{name}</span>
                  <div className="flex items-center gap-2">
                    <div className="w-24 h-1.5 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full rounded-full bg-primary"
                        style={{ width: `${Math.min(weight * 100, 100)}%` }}
                      />
                    </div>
                    <span className="font-mono tabular-nums text-xs w-12 text-right">{(weight * 100).toFixed(1)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Middle: Model Cards Grid */}
      {models.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {models.map((model) => (
            <ModelCard key={model.name} model={model} onRetrain={handleRetrain} />
          ))}
        </div>
      )}

      {/* Bottom: Allocation Chart + Comparison Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {allocation.length > 0 && (
          <AllocationChart data={allocation} />
        )}

        {/* Comparison Table */}
        {models.length > 0 && (
          <div className={`rounded-lg border border-border/50 bg-card overflow-x-auto ${allocation.length > 0 ? "lg:col-span-2" : "lg:col-span-3"}`}>
            <div className="px-4 py-3 border-b">
              <h3 className="text-sm font-semibold">Model Comparison</h3>
            </div>
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
                  <th className="py-2 px-4">Model</th>
                  <th className="py-2 px-4">Type</th>
                  <th className="py-2 px-4">Trained</th>
                  <th className="py-2 px-4">Sharpe</th>
                  <th className="py-2 px-4">Sortino</th>
                  <th className="py-2 px-4">Win Rate</th>
                  <th className="py-2 px-4">Max DD</th>
                  <th className="py-2 px-4">Return</th>
                  <th className="py-2 px-4">Trades</th>
                  <th className="py-2 px-4">P/F</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.name} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-4 font-medium">{m.name}</td>
                    <td className="py-2 px-4 text-xs text-muted-foreground">{m.type.replace("Model", "")}</td>
                    <td className="py-2 px-4">
                      <span className={`inline-block h-2 w-2 rounded-full ${m.is_trained ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
                    </td>
                    <td className="py-2 px-4 font-mono tabular-nums">{m.metrics.sharpe_ratio.toFixed(3)}</td>
                    <td className="py-2 px-4 font-mono tabular-nums">{m.metrics.sortino_ratio.toFixed(3)}</td>
                    <td className="py-2 px-4 font-mono tabular-nums">{(m.metrics.win_rate * 100).toFixed(1)}%</td>
                    <td className="py-2 px-4 font-mono tabular-nums">{(m.metrics.max_drawdown * 100).toFixed(1)}%</td>
                    <td className="py-2 px-4 font-mono tabular-nums">{(m.metrics.total_return * 100).toFixed(1)}%</td>
                    <td className="py-2 px-4 font-mono tabular-nums text-muted-foreground">{m.metrics.num_trades}</td>
                    <td className="py-2 px-4 font-mono tabular-nums">{m.metrics.profit_factor.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
