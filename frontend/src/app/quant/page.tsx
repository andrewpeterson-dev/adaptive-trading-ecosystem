"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Brain, ChevronRight, Loader2, Plus, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { StrategyRecord } from "@/types/strategy";
import { Skeleton } from "@/components/ui/skeleton";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StrategyPerf {
  sharpe: number;
  sortino: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  total_return: number;
  num_trades: number;
  confidence: number;
}

interface CompareStrategy {
  id: number;
  name: string;
  timeframe: string;
  action: string;
  performance: StrategyPerf;
  equity_curve: { date: string; value: number }[];
}

// ── Constants ─────────────────────────────────────────────────────────────────

const PALETTE = [
  "#6366f1", "#10b981", "#f59e0b", "#ef4444",
  "#3b82f6", "#8b5cf6", "#ec4899", "#14b8a6",
];

const RADAR_METRICS: { key: keyof StrategyPerf; label: string; invert?: boolean }[] = [
  { key: "win_rate", label: "Win Rate" },
  { key: "sharpe", label: "Sharpe" },
  { key: "profit_factor", label: "Profit Factor" },
  { key: "max_drawdown", label: "Draw-Control", invert: true },
  { key: "confidence", label: "Confidence" },
  { key: "total_return", label: "Return" },
];

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtPct(n: number) {
  return `${(n * 100).toFixed(1)}%`;
}

function fmtRatio(n: number) {
  return n.toFixed(2);
}

function metricLabel(key: keyof StrategyPerf) {
  switch (key) {
    case "win_rate": return fmtPct;
    case "max_drawdown": return fmtPct;
    case "total_return": return fmtPct;
    case "confidence": return (n: number) => `${n.toFixed(0)}%`;
    default: return fmtRatio;
  }
}

/** Normalise a metric to 0–100 for radar chart. */
function normalise(
  value: number,
  key: keyof StrategyPerf,
  all: CompareStrategy[]
): number {
  const values = all.map((s) => s.performance[key] as number);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const t = (value - min) / range;
  const m = RADAR_METRICS.find((m) => m.key === key);
  return Math.round((m?.invert ? 1 - t : t) * 100);
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function PageSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <Skeleton className="h-12 w-full rounded-xl" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <Skeleton className="h-64 rounded-xl" />
        <Skeleton className="h-64 rounded-xl" />
      </div>
      <Skeleton className="h-48 rounded-xl" />
    </div>
  );
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function QuantPage() {
  const [strategies, setStrategies] = useState<StrategyRecord[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [compareData, setCompareData] = useState<CompareStrategy[]>([]);
  const [strategiesLoading, setStrategiesLoading] = useState(true);
  const [compareLoading, setCompareLoading] = useState(false);
  const [error, setError] = useState("");

  // Load available strategies
  useEffect(() => {
    apiFetch<StrategyRecord[]>("/api/strategies/list")
      .then((data) => {
        setStrategies(data ?? []);
        // Auto-select up to 3
        const ids = (data ?? []).slice(0, 3).map((s) => s.id);
        setSelectedIds(ids);
      })
      .catch((e) => setError(e.message))
      .finally(() => setStrategiesLoading(false));
  }, []);

  const runCompare = useCallback(async () => {
    if (selectedIds.length === 0) return;
    setCompareLoading(true);
    setError("");
    try {
      const data = await apiFetch<{ strategies: CompareStrategy[] }>(
        `/api/quant/compare?ids=${selectedIds.join(",")}`
      );
      setCompareData(data.strategies ?? []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to compare strategies");
    } finally {
      setCompareLoading(false);
    }
  }, [selectedIds]);

  // Auto-compare when selection changes (debounced via useEffect)
  useEffect(() => {
    if (selectedIds.length > 0) runCompare();
  }, [selectedIds]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggleId = (id: number) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id].slice(-6)
    );
  };

  // Build radar data
  const radarData =
    compareData.length > 0
      ? RADAR_METRICS.map(({ key, label }) => {
          const entry: Record<string, string | number> = { metric: label };
          compareData.forEach((s) => {
            entry[s.name] = normalise(s.performance[key] as number, key, compareData);
          });
          return entry;
        })
      : [];

  return (
    <div className="max-w-7xl mx-auto px-4 py-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2">
            <Brain className="h-5 w-5 text-primary" />
            Quant Intelligence
          </h1>
          <p className="text-xs text-muted-foreground mt-0.5">
            Compare strategy performance, risk, and AI confidence side by side
          </p>
        </div>
      </div>

      {/* Strategy selector */}
      <div className="rounded-xl border border-border/50 bg-card p-4 space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Select strategies to compare (up to 6)
        </div>
        {strategiesLoading ? (
          <div className="flex gap-2">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-8 w-28 rounded-lg" />)}
          </div>
        ) : strategies.length === 0 ? (
          <div className="text-sm text-muted-foreground">
            No strategies found.{" "}
            <Link href="/" className="text-primary hover:underline">
              Create one
            </Link>{" "}
            to start comparing.
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            {strategies.map((s, i) => {
              const selected = selectedIds.includes(s.id);
              const color = PALETTE[selectedIds.indexOf(s.id) % PALETTE.length];
              return (
                <button
                  key={s.id}
                  onClick={() => toggleId(s.id)}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium border transition-all ${
                    selected
                      ? "border-transparent text-white"
                      : "border-border/50 text-muted-foreground hover:text-foreground hover:border-border"
                  }`}
                  style={selected ? { backgroundColor: color, borderColor: color } : {}}
                >
                  {s.name}
                  {selected && <X className="h-3 w-3" />}
                </button>
              );
            })}
          </div>
        )}
      </div>

      {error && (
        <div className="rounded-xl border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {compareLoading && (
        <div className="flex items-center justify-center py-12 text-muted-foreground gap-2">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span className="text-sm">Analysing strategies…</span>
        </div>
      )}

      {!compareLoading && compareData.length > 0 && (
        <>
          {/* Side-by-side equity curves */}
          <div className="rounded-xl border border-border/50 bg-card p-4">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
              Equity Curves
            </div>
            <ResponsiveContainer width="100%" height={240}>
              <AreaChart>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="date"
                  type="category"
                  allowDuplicatedCategory={false}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(d: string) => d?.slice(5) ?? ""}
                />
                <YAxis
                  width={60}
                  tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  tickFormatter={(v: number) =>
                    v >= 1000 ? `$${(v / 1000).toFixed(0)}k` : `$${v}`
                  }
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    fontSize: 11,
                    borderRadius: 6,
                  }}
                />
                {compareData.map((s, i) => {
                  const color = PALETTE[i % PALETTE.length];
                  const gradId = `eq${s.id}`;
                  return (
                    <React.Fragment key={s.id}>
                      <defs>
                        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor={color} stopOpacity={0.2} />
                          <stop offset="95%" stopColor={color} stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <Area
                        data={s.equity_curve}
                        dataKey="value"
                        name={s.name}
                        type="monotone"
                        stroke={color}
                        fill={`url(#${gradId})`}
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 4 }}
                      />
                    </React.Fragment>
                  );
                })}
              </AreaChart>
            </ResponsiveContainer>

            {/* Legend */}
            <div className="flex flex-wrap gap-3 mt-3">
              {compareData.map((s, i) => (
                <div key={s.id} className="flex items-center gap-1.5 text-xs">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: PALETTE[i % PALETTE.length] }}
                  />
                  <Link
                    href={`/intelligence/${s.id}`}
                    className="hover:text-foreground text-muted-foreground hover:underline flex items-center gap-0.5"
                  >
                    {s.name}
                    <ChevronRight className="h-3 w-3" />
                  </Link>
                </div>
              ))}
            </div>
          </div>

          {/* Radar + metrics table */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {/* Radar chart */}
            <div className="rounded-xl border border-border/50 bg-card p-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Performance Radar
              </div>
              <ResponsiveContainer width="100%" height={280}>
                <RadarChart data={radarData} outerRadius={100}>
                  <PolarGrid stroke="hsl(var(--border))" />
                  <PolarAngleAxis
                    dataKey="metric"
                    tick={{ fontSize: 10, fill: "hsl(var(--muted-foreground))" }}
                  />
                  <PolarRadiusAxis
                    angle={30}
                    domain={[0, 100]}
                    tick={{ fontSize: 8, fill: "hsl(var(--muted-foreground))" }}
                  />
                  {compareData.map((s, i) => (
                    <Radar
                      key={s.id}
                      name={s.name}
                      dataKey={s.name}
                      stroke={PALETTE[i % PALETTE.length]}
                      fill={PALETTE[i % PALETTE.length]}
                      fillOpacity={0.12}
                      strokeWidth={2}
                    />
                  ))}
                  <Tooltip
                    contentStyle={{
                      background: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      fontSize: 11,
                      borderRadius: 6,
                    }}
                  />
                </RadarChart>
              </ResponsiveContainer>
            </div>

            {/* Metric comparison bar charts */}
            <div className="rounded-xl border border-border/50 bg-card p-4 space-y-4">
              <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Key Metrics
              </div>
              {(
                [
                  { key: "sharpe" as const, label: "Sharpe Ratio" },
                  { key: "win_rate" as const, label: "Win Rate" },
                  { key: "total_return" as const, label: "Total Return" },
                ] as { key: keyof StrategyPerf; label: string }[]
              ).map(({ key, label }) => (
                <div key={key}>
                  <div className="text-[10px] text-muted-foreground mb-1">{label}</div>
                  {compareData.map((s, i) => {
                    const val = s.performance[key] as number;
                    const displayVal =
                      key === "sharpe" ? val.toFixed(2) : fmtPct(val);
                    const maxVal = Math.max(
                      ...compareData.map((x) => Math.abs(x.performance[key] as number))
                    );
                    const barPct = maxVal > 0 ? (Math.abs(val) / maxVal) * 100 : 0;
                    const color = PALETTE[i % PALETTE.length];
                    return (
                      <div key={s.id} className="flex items-center gap-2 mb-1">
                        <div
                          className="text-[10px] truncate"
                          style={{ color, width: 80, flexShrink: 0 }}
                        >
                          {s.name}
                        </div>
                        <div className="flex-1 h-4 rounded-full bg-muted/30 overflow-hidden">
                          <div
                            className="h-full rounded-full transition-all duration-500"
                            style={{ width: `${barPct}%`, backgroundColor: color, opacity: 0.8 }}
                          />
                        </div>
                        <div
                          className="text-[10px] font-mono w-12 text-right"
                          style={{ color }}
                        >
                          {displayVal}
                        </div>
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          </div>

          {/* Full metrics table */}
          <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-4 py-3 border-b border-border/40">
              Full Comparison Table
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border/40 bg-muted/20">
                    <th className="py-2 px-4 text-left text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Strategy
                    </th>
                    {["Sharpe", "Sortino", "Win Rate", "Profit Factor", "Max DD", "Return", "Trades", "Conf"].map(
                      (h) => (
                        <th
                          key={h}
                          className="py-2 px-3 text-right text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
                        >
                          {h}
                        </th>
                      )
                    )}
                    <th className="py-2 px-3 text-center text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                      Detail
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.map((s, i) => {
                    const p = s.performance;
                    const color = PALETTE[i % PALETTE.length];
                    return (
                      <tr key={s.id} className="border-b border-border/30 hover:bg-muted/10 transition-colors">
                        <td className="py-3 px-4">
                          <div className="flex items-center gap-2">
                            <span
                              className="h-2 w-2 rounded-full shrink-0"
                              style={{ backgroundColor: color }}
                            />
                            <div>
                              <div className="text-xs font-medium">{s.name}</div>
                              <div className="text-[10px] text-muted-foreground">
                                {s.timeframe} · {s.action}
                              </div>
                            </div>
                          </div>
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.sharpe > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {p.sharpe.toFixed(2)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.sortino > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {p.sortino.toFixed(2)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.win_rate > 0.5 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {fmtPct(p.win_rate)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.profit_factor > 1 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {p.profit_factor.toFixed(2)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.max_drawdown > -0.15 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {fmtPct(p.max_drawdown)}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.total_return > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {p.total_return >= 0 ? "+" : ""}
                          {fmtPct(p.total_return)}
                        </td>
                        <td className="py-3 px-3 text-right font-mono text-xs text-muted-foreground">
                          {p.num_trades}
                        </td>
                        <td
                          className={`py-3 px-3 text-right font-mono text-xs ${
                            p.confidence >= 70
                              ? "text-emerald-400"
                              : p.confidence >= 50
                              ? "text-amber-400"
                              : "text-red-400"
                          }`}
                        >
                          {p.confidence.toFixed(0)}%
                        </td>
                        <td className="py-3 px-3 text-center">
                          <Link
                            href={`/intelligence/${s.id}`}
                            className="inline-flex items-center gap-0.5 text-[10px] text-primary hover:underline"
                          >
                            View <ChevronRight className="h-3 w-3" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {!compareLoading && compareData.length === 0 && !strategiesLoading && strategies.length === 0 && (
        <div className="rounded-xl border border-dashed border-border/50 p-12 text-center space-y-3">
          <Brain className="h-10 w-10 text-muted-foreground/40 mx-auto" />
          <div className="text-sm text-muted-foreground">No strategies to compare yet.</div>
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline"
          >
            <Plus className="h-3.5 w-3.5" /> Build your first strategy
          </Link>
        </div>
      )}
    </div>
  );
}
