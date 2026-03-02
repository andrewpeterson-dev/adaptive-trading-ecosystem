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
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { ModelInfo, AllocationEntry, EquityCurvePoint } from "@/types/portfolio";

const PIE_COLORS = ["#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"];

function MetricCell({ value, format }: { value: number | null; format?: string }) {
  if (value === null || value === undefined) return <span className="text-muted-foreground">—</span>;
  if (format === "percent") return <span>{(value * 100).toFixed(1)}%</span>;
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

  const fetchAll = useCallback(async () => {
    try {
      const [eqRes, allocRes, modRes, regRes] = await Promise.allSettled([
        apiFetch<any>("/api/dashboard/equity-curve"),
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
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error && !models.length && !equityCurve.length) {
    return (
      <div className="text-center py-20 space-y-3">
        <Unplug className="h-10 w-10 text-muted-foreground/40 mx-auto" />
        <h2 className="text-lg font-semibold">No Portfolio Data</h2>
        <p className="text-sm text-muted-foreground max-w-md mx-auto">
          Train models and connect a broker to view portfolio analytics, equity curves, and allocation breakdowns.
        </p>
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Portfolio</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {models.length} model{models.length !== 1 ? "s" : ""} deployed
          </p>
        </div>
        {regime && (
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-muted-foreground" />
            <span className="text-xs font-medium text-muted-foreground uppercase tracking-wider">
              Regime:
            </span>
            <span className="text-xs font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
              {regimeLabel}
            </span>
          </div>
        )}
      </div>

      {/* Equity Curve */}
      {equityCurve.length > 0 && (
        <EquityCurveChart data={equityCurve} height={300} />
      )}

      {/* Allocation + Model Table */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Allocation Pie */}
        {pieData.length > 0 && (
          <div className="rounded-lg border border-border/50 bg-card p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground uppercase tracking-wider mb-3">
              <Layers className="h-4 w-4" />
              Capital Allocation
            </div>
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={90}
                  paddingAngle={2}
                  label={({ name, value }) => `${name} ${value.toFixed(0)}%`}
                >
                  {pieData.map((_, i) => (
                    <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "6px",
                    fontSize: "12px",
                  }}
                  formatter={(val) => [`${Number(val ?? 0).toFixed(1)}%`, "Weight"]}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}

        {/* Model Performance Table */}
        <div className={`rounded-lg border border-border/50 bg-card overflow-x-auto ${pieData.length > 0 ? "lg:col-span-2" : "lg:col-span-3"}`}>
          <div className="px-4 py-3 border-b flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-muted-foreground" />
            <h3 className="text-sm font-semibold">Model Performance</h3>
          </div>
          {models.length === 0 ? (
            <div className="py-8 text-center text-muted-foreground text-sm">No models trained yet</div>
          ) : (
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
                  <th className="py-2 px-4">Model</th>
                  <th className="py-2 px-4">Type</th>
                  <th className="py-2 px-4">Active</th>
                  <th className="py-2 px-4">Sharpe</th>
                  <th className="py-2 px-4">Win Rate</th>
                  <th className="py-2 px-4">Max DD</th>
                  <th className="py-2 px-4">Return</th>
                  <th className="py-2 px-4">Trades</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => (
                  <tr key={m.name} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                    <td className="py-2 px-4 font-medium">{m.name}</td>
                    <td className="py-2 px-4 text-xs text-muted-foreground">{m.model_type}</td>
                    <td className="py-2 px-4">
                      <span className={`inline-block h-2 w-2 rounded-full ${m.is_active ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
                    </td>
                    <td className="py-2 px-4 font-mono tabular-nums"><MetricCell value={m.sharpe_ratio} format="ratio" /></td>
                    <td className="py-2 px-4 font-mono tabular-nums"><MetricCell value={m.win_rate} format="percent" /></td>
                    <td className="py-2 px-4 font-mono tabular-nums"><MetricCell value={m.max_drawdown} format="percent" /></td>
                    <td className="py-2 px-4 font-mono tabular-nums"><MetricCell value={m.total_return} format="percent" /></td>
                    <td className="py-2 px-4 font-mono tabular-nums text-muted-foreground">{m.num_trades}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
