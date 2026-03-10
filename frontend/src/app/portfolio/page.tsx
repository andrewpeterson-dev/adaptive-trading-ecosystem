"use client";

import React, { useEffect, useState, useCallback } from "react";
import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Tooltip,
  Legend,
} from "recharts";
import {
  Loader2,
  TrendingUp,
  Layers,
  Activity,
  Unplug,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradingMode } from "@/hooks/useTradingMode";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { ModelInfo, AllocationEntry, EquityCurvePoint } from "@/types/portfolio";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

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
        setModels(data.models || data || []);
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

  if (loading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !models.length && !equityCurve.length) {
    return (
      <div className="text-center py-32 space-y-4">
        <div className="inline-flex items-center justify-center h-14 w-14 rounded-full bg-muted/50 border border-border/50 mx-auto">
          <Unplug className="h-6 w-6 text-muted-foreground/60" />
        </div>
        <div>
          <h2 className="text-base font-semibold">No portfolio data</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Train models and connect a broker to view portfolio analytics, equity curves, and allocation breakdowns.
          </p>
        </div>
      </div>
    );
  }

  const pieData = allocation.map((a) => ({
    name: a.model_name,
    value: a.weight * 100,
  }));

  const regimeLabel = regime?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || "Unknown";

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-lg font-semibold tracking-tight">Portfolio</h1>
            <span
              className={`text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-widest border ${
                mode === "live"
                  ? "bg-emerald-500/10 text-emerald-400 border-emerald-500/25"
                  : "bg-muted text-muted-foreground border-border/50"
              }`}
            >
              {mode === "live" ? "Live" : "Paper"}
            </span>
          </div>
          <p className="text-xs text-muted-foreground mt-0.5 font-mono">
            {models.length} model{models.length !== 1 ? "s" : ""} deployed
          </p>
        </div>
        {regime && (
          <div className="flex items-center gap-2">
            <Activity className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              Regime
            </span>
            <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest bg-primary/10 text-primary border border-primary/20">
              {regimeLabel}
            </span>
          </div>
        )}
      </div>

      {/* Equity Curve */}
      {equityCurve.length > 0 && (
        <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
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

      {/* Allocation + Model Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        {/* Allocation Pie */}
        {pieData.length > 0 && (
          <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
            <div className="px-4 py-3 border-b border-border/50">
              <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest flex items-center gap-2">
                <Layers className="h-3.5 w-3.5" />
                Capital Allocation
              </div>
            </div>
            <div className="p-4">
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={90}
                    paddingAngle={2}
                    label={({ name, value }) => `${name} ${value.toFixed(1)}%`}
                    labelLine={{ stroke: "hsl(var(--muted-foreground))", strokeWidth: 0.5 }}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "8px",
                      fontSize: "11px",
                      color: "hsl(var(--foreground))",
                    }}
                    formatter={(val) => [`${Number(val ?? 0).toFixed(1)}%`, "Weight"]}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Model Performance Table */}
        <div className={`rounded-xl border border-border/50 bg-card overflow-hidden ${pieData.length > 0 ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <div className="px-4 py-3 border-b border-border/50 flex items-center gap-2">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
            <div className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">
              Model Performance
            </div>
          </div>
          {models.length === 0 ? (
            <div className="py-12 flex flex-col items-center gap-3 text-center px-4">
              <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-muted/50 border border-border/50">
                <TrendingUp className="h-4 w-4 text-muted-foreground/50" />
              </div>
              <div>
                <div className="text-sm font-medium text-muted-foreground">No models trained yet</div>
                <div className="text-xs text-muted-foreground/60 mt-0.5">Train a model to see performance metrics</div>
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead>
                  <tr className="border-b border-border/50 bg-muted/20 text-[10px] text-muted-foreground uppercase tracking-widest">
                    <th className="py-2.5 px-4 font-semibold">Model</th>
                    <th className="py-2.5 px-4 font-semibold">Type</th>
                    <th className="py-2.5 px-4 font-semibold">Active</th>
                    <th className="py-2.5 px-4 font-semibold">Sharpe</th>
                    <th className="py-2.5 px-4 font-semibold">Win Rate</th>
                    <th className="py-2.5 px-4 font-semibold">Max DD</th>
                    <th className="py-2.5 px-4 font-semibold">Return</th>
                    <th className="py-2.5 px-4 font-semibold">Trades</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((m, i) => (
                    <tr
                      key={m.name}
                      className={`border-b border-border/40 hover:bg-muted/20 transition-colors ${
                        i % 2 === 1 ? "bg-muted/5" : ""
                      }`}
                    >
                      <td className="py-2.5 px-4 font-medium text-sm">{m.name}</td>
                      <td className="py-2.5 px-4 text-xs text-muted-foreground uppercase tracking-wide">{m.model_type}</td>
                      <td className="py-2.5 px-4">
                        <span className={`inline-flex items-center gap-1 text-xs font-medium ${m.is_active ? "text-emerald-400" : "text-muted-foreground/50"}`}>
                          <span className={`h-1.5 w-1.5 rounded-full ${m.is_active ? "bg-emerald-400" : "bg-muted-foreground/30"}`} />
                          {m.is_active ? "On" : "Off"}
                        </span>
                      </td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums"><MetricCell value={m.sharpe_ratio} format="ratio" /></td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums"><MetricCell value={m.win_rate} format="percent" /></td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums"><MetricCell value={m.max_drawdown} format="percent" /></td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums"><MetricCell value={m.total_return} format="percent" /></td>
                      <td className="py-2.5 px-4 font-mono text-sm tabular-nums text-muted-foreground">{m.num_trades}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
