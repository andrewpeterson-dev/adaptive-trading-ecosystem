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
import { BarChart3, Brain, ChevronRight, Loader2, Plus, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import type { StrategyRecord } from "@/types/strategy";
import { Skeleton } from "@/components/ui/skeleton";
import { PageHeader } from "@/components/layout/PageHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { EmptyState } from "@/components/ui/empty-state";

// ── Types ─────────────────────────────────────────────────────────────────────

interface StrategyPerf {
  sharpe: number | null;
  sortino: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  max_drawdown: number | null;
  total_return: number | null;
  num_trades: number;
  confidence: number | null;
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

/** Safe number accessor — returns 0 for null. */
function safeNum(v: number | null | undefined): number {
  return v ?? 0;
}

/** Format metric value or return dash for null. */
function safePct(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return fmtPct(n);
}

function safeRatio(n: number | null | undefined): string {
  if (n == null) return "\u2014";
  return fmtRatio(n);
}

/** Check if any strategy in the compare set has real performance data. */
function hasAnyPerfData(strategies: CompareStrategy[]): boolean {
  return strategies.some(
    (s) => s.equity_curve.length > 0 || s.performance.sharpe != null
  );
}

/** Normalise a metric to 0–100 for radar chart. */
function normalise(
  value: number | null,
  key: keyof StrategyPerf,
  all: CompareStrategy[]
): number {
  const values = all.map((s) => safeNum(s.performance[key] as number | null));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const t = (safeNum(value) - min) / range;
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
    apiFetch<{ strategies: StrategyRecord[] } | StrategyRecord[]>("/api/strategies/list")
      .then((data) => {
        const list = Array.isArray(data) ? data : data.strategies ?? [];
        setStrategies(list);
        // Auto-select up to 3
        const ids = list.slice(0, 3).map((s) => s.id);
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
  const hasPerfData = hasAnyPerfData(compareData);
  const radarData =
    compareData.length > 0 && hasPerfData
      ? RADAR_METRICS.map(({ key, label }) => {
          const entry: Record<string, string | number> = { metric: label };
          compareData.forEach((s) => {
            entry[s.name] = normalise(s.performance[key] as number | null, key, compareData);
          });
          return entry;
        })
      : [];

  return (
    <div className="app-page">
      <PageHeader
        eyebrow="Research"
        title="Quant Intelligence"
        description="Compare strategy performance, risk posture, and AI confidence side by side before you promote a setup into production."
        badge={
          <Badge variant="info">
            <Brain className="h-3.5 w-3.5" />
            Compare up to 6
          </Badge>
        }
        meta={
          <Badge className="font-mono tracking-normal">
            {selectedIds.length} selected
          </Badge>
        }
      />

      <div className="app-panel p-4 md:p-5 space-y-3">
        <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Select strategies to compare (up to 6)
        </div>
        {strategiesLoading ? (
          <div className="flex gap-2">
            {[...Array(3)].map((_, i) => <Skeleton key={i} className="h-8 w-28 rounded-lg" />)}
          </div>
        ) : strategies.length === 0 ? (
          <EmptyState
            title="No strategies found"
            description={
              <>
                Create a strategy first, then return here to compare performance,
                risk, and confidence.
              </>
            }
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/">Create strategy</Link>
              </Button>
            }
            className="py-10"
          />
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
        <div className="rounded-[20px] border border-red-400/20 bg-red-400/5 p-3 text-sm text-red-300">
          {error}
        </div>
      )}

      {compareLoading && (
        <div className="app-panel">
          <EmptyState
            icon={<Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />}
            title="Analysing strategies"
            description="Building the comparison set, normalising metrics, and preparing the visualization stack."
            className="py-12"
          />
        </div>
      )}

      {!compareLoading && compareData.length > 0 && !hasPerfData && (
        <div className="app-panel">
          <EmptyState
            icon={<BarChart3 className="h-5 w-5 text-muted-foreground/70" />}
            title="No performance data available"
            description="Run your strategies in paper or live mode to generate performance data for comparison."
            className="py-12"
          />
        </div>
      )}

      {!compareLoading && compareData.length > 0 && hasPerfData && (
        <>
          <div className="app-panel p-4 md:p-5">
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

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="app-panel p-4 md:p-5">
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

            <div className="app-panel p-4 md:p-5 space-y-4">
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
                    const val = s.performance[key];
                    const displayVal =
                      val == null
                        ? "\u2014"
                        : key === "sharpe"
                        ? (val as number).toFixed(2)
                        : fmtPct(val as number);
                    const maxVal = Math.max(
                      ...compareData.map((x) => Math.abs(safeNum(x.performance[key] as number | null)))
                    );
                    const barPct = val != null && maxVal > 0 ? (Math.abs(val as number) / maxVal) * 100 : 0;
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

          <div className="app-table-shell">
            <div className="text-xs font-semibold uppercase tracking-wider text-muted-foreground px-4 py-3 border-b border-border/40">
              Full Comparison Table
            </div>
            <div className="overflow-x-auto">
              <table className="app-table">
                <thead>
                  <tr>
                    <th>Strategy</th>
                    {["Sharpe", "Sortino", "Win Rate", "Profit Factor", "Max DD", "Return", "Trades", "Conf"].map(
                      (h) => <th key={h} className="text-right">{h}</th>
                    )}
                    <th className="text-center">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {compareData.map((s, i) => {
                    const p = s.performance;
                    const color = PALETTE[i % PALETTE.length];
                    return (
                      <tr key={s.id}>
                        <td>
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
                          className={`text-right font-mono text-xs ${
                            p.sharpe == null ? "text-muted-foreground" : p.sharpe > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {safeRatio(p.sharpe)}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.sortino == null ? "text-muted-foreground" : p.sortino > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {safeRatio(p.sortino)}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.win_rate == null ? "text-muted-foreground" : p.win_rate > 0.5 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {safePct(p.win_rate)}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.profit_factor == null ? "text-muted-foreground" : p.profit_factor > 1 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {safeRatio(p.profit_factor)}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.max_drawdown == null ? "text-muted-foreground" : p.max_drawdown > -0.15 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {safePct(p.max_drawdown)}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.total_return == null ? "text-muted-foreground" : p.total_return > 0 ? "text-emerald-400" : "text-red-400"
                          }`}
                        >
                          {p.total_return == null ? "\u2014" : `${p.total_return >= 0 ? "+" : ""}${fmtPct(p.total_return)}`}
                        </td>
                        <td className="text-right font-mono text-xs text-muted-foreground">
                          {p.num_trades}
                        </td>
                        <td
                          className={`text-right font-mono text-xs ${
                            p.confidence == null
                              ? "text-muted-foreground"
                              : p.confidence >= 70
                              ? "text-emerald-400"
                              : p.confidence >= 50
                              ? "text-amber-400"
                              : "text-red-400"
                          }`}
                        >
                          {p.confidence != null ? `${p.confidence.toFixed(0)}%` : "\u2014"}
                        </td>
                        <td className="text-center">
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
        <div className="app-panel">
          <EmptyState
            icon={<Brain className="h-5 w-5 text-muted-foreground/70" />}
            title="No strategies to compare yet"
            description="Build and save a strategy first, then return here to compare risk, return, and AI confidence."
            action={
              <Button asChild variant="primary" size="sm">
                <Link href="/">
                  <Plus className="h-3.5 w-3.5" />
                  Build your first strategy
                </Link>
              </Button>
            }
            className="py-12"
          />
        </div>
      )}
    </div>
  );
}
