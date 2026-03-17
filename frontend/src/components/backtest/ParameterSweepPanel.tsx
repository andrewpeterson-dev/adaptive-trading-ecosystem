"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  Loader2,
  Grid3X3,
  Trophy,
  ChevronDown,
  Zap,
  ArrowRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import type { StrategyRecord } from "@/types/strategy";
import type { SweepResult, SweepDataPoint } from "@/types/backtest";

// ── Types ───────────────────────────────────────────────────────────────

interface ParamRange {
  name: string;
  label: string;
  min: number;
  max: number;
  step: number;
}

type OptimizeMetric = "sharpe" | "total_return" | "win_rate" | "profit_factor";

const METRIC_OPTIONS: { value: OptimizeMetric; label: string }[] = [
  { value: "sharpe", label: "Sharpe Ratio" },
  { value: "total_return", label: "Total Return" },
  { value: "win_rate", label: "Win Rate" },
  { value: "profit_factor", label: "Profit Factor" },
];

// ── Color interpolation helper ──────────────────────────────────────────

function metricColor(value: number, min: number, max: number): string {
  if (max === min) return "rgba(250, 204, 21, 0.7)"; // yellow fallback
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  // red → yellow → green
  if (t < 0.5) {
    const s = t * 2;
    const r = Math.round(239 + (250 - 239) * s);
    const g = Math.round(68 + (204 - 68) * s);
    const b = Math.round(68 + (21 - 68) * s);
    return `rgba(${r}, ${g}, ${b}, 0.75)`;
  }
  const s = (t - 0.5) * 2;
  const r = Math.round(250 + (34 - 250) * s);
  const g = Math.round(204 + (197 - 204) * s);
  const b = Math.round(21 + (94 - 21) * s);
  return `rgba(${r}, ${g}, ${b}, 0.75)`;
}

function metricTextColor(value: number, min: number, max: number): string {
  if (max === min) return "rgba(255,255,255,0.9)";
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  // dark text on yellow, light text on extremes
  if (t > 0.3 && t < 0.7) return "rgba(0,0,0,0.85)";
  return "rgba(255,255,255,0.95)";
}

// ── Mini sparkline SVG ──────────────────────────────────────────────────

function Sparkline({ data }: { data: { date: string; value: number }[] }) {
  if (!data || data.length < 2) return null;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 120;
  const h = 32;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * h;
      return `${x},${y}`;
    })
    .join(" ");
  const isPositive = values[values.length - 1] >= values[0];
  return (
    <svg width={w} height={h} className="block">
      <polyline
        fill="none"
        stroke={isPositive ? "#22c55e" : "#ef4444"}
        strokeWidth="1.5"
        points={points}
      />
    </svg>
  );
}

// ── Extract tuneable parameters from strategy conditions ────────────────

function extractParamRanges(strategy: StrategyRecord): ParamRange[] {
  const seen = new Set<string>();
  const ranges: ParamRange[] = [];
  const allConditions = [
    ...(strategy.conditions || []),
    ...(strategy.condition_groups || []).flatMap((g) => g.conditions),
  ];
  for (const cond of allConditions) {
    if (!cond.params) continue;
    for (const [key, val] of Object.entries(cond.params)) {
      const compositeKey = `${cond.indicator}_${key}`;
      if (seen.has(compositeKey)) continue;
      seen.add(compositeKey);
      const numVal = typeof val === "number" ? val : parseFloat(String(val));
      if (isNaN(numVal)) continue;
      // Default range: 50% to 200% of current value, step = ~10% of value
      const base = Math.max(1, Math.abs(numVal));
      const lo = Math.max(1, Math.round(numVal * 0.5));
      const hi = Math.round(numVal * 2);
      const step = Math.max(1, Math.round(base * 0.1));
      ranges.push({
        name: compositeKey,
        label: `${cond.indicator} ${key}`,
        min: lo,
        max: hi,
        step,
      });
    }
  }
  return ranges;
}

// ── Main Component ──────────────────────────────────────────────────────

interface ParameterSweepPanelProps {
  strategy: StrategyRecord;
  symbol: string;
  lookbackDays: number;
}

export function ParameterSweepPanel({
  strategy,
  symbol,
  lookbackDays,
}: ParameterSweepPanelProps) {
  // Derive default parameter ranges from strategy
  const defaultRanges = useMemo(() => extractParamRanges(strategy), [strategy]);

  const [paramRanges, setParamRanges] = useState<ParamRange[]>(() =>
    defaultRanges.length >= 2 ? defaultRanges.slice(0, 2) : defaultRanges
  );
  const [metric, setMetric] = useState<OptimizeMetric>("sharpe");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<SweepResult | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{
    row: number;
    col: number;
  } | null>(null);

  // Build parameter_ranges payload
  const parameterRangesPayload = useMemo(() => {
    const out: Record<string, { min: number; max: number; step: number }> = {};
    for (const pr of paramRanges) {
      out[pr.name] = { min: pr.min, max: pr.max, step: pr.step };
    }
    return out;
  }, [paramRanges]);

  const totalCombinations = useMemo(() => {
    return paramRanges.reduce((acc, pr) => {
      const count = Math.max(1, Math.floor((pr.max - pr.min) / pr.step) + 1);
      return acc * count;
    }, 1);
  }, [paramRanges]);

  const updateRange = useCallback(
    (index: number, field: "min" | "max" | "step", value: number) => {
      setParamRanges((prev) => {
        const next = [...prev];
        next[index] = { ...next[index], [field]: value };
        return next;
      });
    },
    []
  );

  const runSweep = useCallback(async () => {
    setRunning(true);
    setError(null);
    setSweepResult(null);
    try {
      const data = await apiFetch<SweepResult>(
        "/api/strategies/parameter-sweep",
        {
          method: "POST",
          timeoutMs: 300_000,
          body: JSON.stringify({
            strategy_id: strategy.id,
            symbol,
            conditions: strategy.conditions,
            exit_conditions: [],
            parameter_ranges: parameterRangesPayload,
            metric,
            timeframe: strategy.timeframe || "1D",
            lookback_days: lookbackDays,
          }),
        }
      );
      setSweepResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Parameter sweep failed");
    } finally {
      setRunning(false);
    }
  }, [
    strategy,
    symbol,
    lookbackDays,
    parameterRangesPayload,
    metric,
  ]);

  // Build matrix data from sweep result
  const {
    xAxis,
    yAxis,
    xLabel,
    yLabel,
    matrix,
    minVal,
    maxVal,
    bestRow,
    bestCol,
    top5,
  } = useMemo(() => {
    if (!sweepResult) {
      return {
        xAxis: [] as number[],
        yAxis: [] as number[],
        xLabel: "",
        yLabel: "",
        matrix: [] as number[][],
        minVal: 0,
        maxVal: 1,
        bestRow: -1,
        bestCol: -1,
        top5: [] as SweepDataPoint[],
      };
    }

    const axes = Object.entries(sweepResult.param_axes);
    const xLabel = axes[0]?.[0] ?? "Param 1";
    const yLabel = axes[1]?.[0] ?? "Param 2";
    const xAxis = axes[0]?.[1] ?? [];
    const yAxis = axes[1]?.[1] ?? [];

    // Use pre-computed matrix or build from heatmap_data
    let mat: number[][] = sweepResult.matrix ?? [];
    if (mat.length === 0 && sweepResult.heatmap_data.length > 0) {
      mat = Array.from({ length: yAxis.length }, () =>
        Array(xAxis.length).fill(NaN)
      );
      for (const point of sweepResult.heatmap_data) {
        const xi = xAxis.indexOf(point.params[xLabel]);
        const yi = yAxis.indexOf(point.params[yLabel]);
        if (xi >= 0 && yi >= 0) {
          mat[yi][xi] = point.value;
        }
      }
    }

    const allVals = mat.flat().filter((v) => !isNaN(v));
    const minVal = allVals.length > 0 ? Math.min(...allVals) : 0;
    const maxVal = allVals.length > 0 ? Math.max(...allVals) : 1;

    // Find best cell
    let bestRow = -1;
    let bestCol = -1;
    let bestVal = -Infinity;
    for (let r = 0; r < mat.length; r++) {
      for (let c = 0; c < (mat[r]?.length ?? 0); c++) {
        if (!isNaN(mat[r][c]) && mat[r][c] > bestVal) {
          bestVal = mat[r][c];
          bestRow = r;
          bestCol = c;
        }
      }
    }

    // Top 5 combos
    const sorted = [...sweepResult.heatmap_data].sort(
      (a, b) => b.value - a.value
    );
    const top5 = sorted.slice(0, 5);

    return { xAxis, yAxis, xLabel, yLabel, matrix: mat, minVal, maxVal, bestRow, bestCol, top5 };
  }, [sweepResult]);

  // Find best data point for metrics display
  const bestDataPoint = useMemo(() => {
    if (!sweepResult) return null;
    return sweepResult.heatmap_data.find((d) => {
      const bp = sweepResult.best_params;
      return Object.keys(bp).every((k) => d.params[k] === bp[k]);
    }) ?? null;
  }, [sweepResult]);

  return (
    <div className="grid grid-cols-1 gap-3 lg:grid-cols-[240px_1fr_260px]">
      {/* ── Left Sidebar: Sweep Config ─────────────────────────────────── */}
      <div className="space-y-3">
        <div className="app-panel p-3">
          <div className="app-label mb-2">Strategy</div>
          <div className="text-sm font-medium truncate">{strategy.name}</div>
          <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span className="font-mono">{symbol}</span>
            <span>-</span>
            <span className="font-mono">{strategy.timeframe || "1D"}</span>
          </div>
        </div>

        {/* Parameter ranges */}
        <div className="app-panel p-3 space-y-3">
          <div className="app-label">Parameter Ranges</div>
          {paramRanges.length === 0 && (
            <div className="text-xs text-muted-foreground">
              No tuneable parameters detected in this strategy.
            </div>
          )}
          {paramRanges.map((pr, i) => (
            <div key={pr.name} className="space-y-1.5">
              <div className="text-xs font-medium text-muted-foreground truncate">
                {pr.label}
              </div>
              <div className="grid grid-cols-3 gap-1.5">
                <div>
                  <label className="text-[10px] text-muted-foreground/70">Min</label>
                  <input
                    type="number"
                    value={pr.min}
                    onChange={(e) =>
                      updateRange(i, "min", parseFloat(e.target.value) || 1)
                    }
                    className="w-full rounded-md border border-border/60 bg-card px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring/50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground/70">Max</label>
                  <input
                    type="number"
                    value={pr.max}
                    onChange={(e) =>
                      updateRange(i, "max", parseFloat(e.target.value) || 100)
                    }
                    className="w-full rounded-md border border-border/60 bg-card px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring/50"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-muted-foreground/70">Step</label>
                  <input
                    type="number"
                    value={pr.step}
                    onChange={(e) =>
                      updateRange(i, "step", Math.max(1, parseFloat(e.target.value) || 1))
                    }
                    className="w-full rounded-md border border-border/60 bg-card px-2 py-1 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-ring/50"
                  />
                </div>
              </div>
              {/* Range preview bar */}
              <div className="flex items-center gap-1.5 text-[10px] text-muted-foreground font-mono">
                <span>{pr.min}</span>
                <div className="flex-1 h-1 rounded-full bg-muted/40 overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500/50"
                    style={{ width: "100%" }}
                  />
                </div>
                <span>{pr.max}</span>
              </div>
            </div>
          ))}
        </div>

        {/* Optimize for */}
        <div className="app-panel p-3 space-y-2">
          <div className="app-label">Optimize For</div>
          <div className="relative">
            <select
              value={metric}
              onChange={(e) => setMetric(e.target.value as OptimizeMetric)}
              className="w-full appearance-none rounded-md border border-border/60 bg-card px-2 py-1.5 pr-7 text-xs focus:outline-none focus:ring-1 focus:ring-ring/50"
            >
              {METRIC_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
          </div>
          <div className="text-[10px] text-muted-foreground font-mono">
            {totalCombinations.toLocaleString()} combinations
          </div>
        </div>

        {/* Run button */}
        <Button
          onClick={runSweep}
          disabled={running || paramRanges.length < 2}
          variant="primary"
          className="w-full"
          size="sm"
        >
          {running ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Zap className="h-3.5 w-3.5" />
          )}
          {running ? "Sweeping..." : "Run Sweep"}
        </Button>

        {error && (
          <div className="rounded-md border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-300">
            {error}
          </div>
        )}
      </div>

      {/* ── Center: Heatmap Grid ───────────────────────────────────────── */}
      <div className="app-panel p-3 min-h-[400px] flex flex-col">
        {!sweepResult && !running && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3 text-muted-foreground">
            <Grid3X3 className="h-10 w-10 opacity-30" />
            <div className="text-sm">Configure parameters and run sweep</div>
            <div className="text-xs">The heatmap will appear here</div>
          </div>
        )}

        {running && (
          <div className="flex-1 flex flex-col items-center justify-center gap-3">
            <Loader2 className="h-8 w-8 animate-spin text-blue-400" />
            <div className="text-sm text-muted-foreground">
              Running {totalCombinations.toLocaleString()} backtests...
            </div>
          </div>
        )}

        {sweepResult && matrix.length > 0 && (
          <div className="flex-1 flex flex-col">
            <div className="app-label mb-2 flex items-center gap-2">
              <Grid3X3 className="h-3.5 w-3.5" />
              Parameter Sweep Heatmap
            </div>

            {/* Heatmap grid */}
            <div className="flex-1 overflow-auto">
              <div className="inline-block min-w-full">
                {/* Column headers (X axis) */}
                <div className="flex">
                  {/* Corner spacer */}
                  <div className="w-14 shrink-0" />
                  {xAxis.map((xVal) => (
                    <div
                      key={xVal}
                      className="flex-1 min-w-[48px] text-center text-[10px] font-mono text-muted-foreground pb-1"
                    >
                      {xVal}
                    </div>
                  ))}
                </div>

                {/* Grid rows */}
                {yAxis.map((yVal, rowIdx) => (
                  <div key={yVal} className="flex">
                    {/* Row label (Y axis) */}
                    <div className="w-14 shrink-0 flex items-center justify-end pr-2 text-[10px] font-mono text-muted-foreground">
                      {yVal}
                    </div>
                    {/* Cells */}
                    {xAxis.map((_, colIdx) => {
                      const val = matrix[rowIdx]?.[colIdx] ?? NaN;
                      const isNan = isNaN(val);
                      const isBest =
                        rowIdx === bestRow && colIdx === bestCol;
                      const isHovered =
                        hoveredCell?.row === rowIdx &&
                        hoveredCell?.col === colIdx;

                      return (
                        <div
                          key={colIdx}
                          className="flex-1 min-w-[48px] aspect-square flex items-center justify-center text-[10px] font-mono font-medium cursor-default transition-transform"
                          style={{
                            backgroundColor: isNan
                              ? "rgba(100,100,100,0.15)"
                              : metricColor(val, minVal, maxVal),
                            color: isNan
                              ? "rgba(100,100,100,0.4)"
                              : metricTextColor(val, minVal, maxVal),
                            border: isBest
                              ? "2px solid #f59e0b"
                              : isHovered
                              ? "1px solid rgba(255,255,255,0.4)"
                              : "1px solid rgba(255,255,255,0.06)",
                            borderRadius: "4px",
                            margin: "1px",
                            transform: isHovered ? "scale(1.08)" : "none",
                            zIndex: isHovered ? 10 : 1,
                            boxShadow: isBest
                              ? "0 0 12px rgba(245, 158, 11, 0.4)"
                              : "none",
                          }}
                          onMouseEnter={() =>
                            setHoveredCell({ row: rowIdx, col: colIdx })
                          }
                          onMouseLeave={() => setHoveredCell(null)}
                          title={
                            isNan
                              ? "N/A"
                              : `${yLabel}=${yAxis[rowIdx]}, ${xLabel}=${xAxis[colIdx]}: ${val.toFixed(3)}`
                          }
                        >
                          {isNan ? "-" : val.toFixed(2)}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            </div>

            {/* Axis labels */}
            <div className="mt-2 flex items-center justify-between text-[10px] text-muted-foreground">
              <span className="font-medium">
                Y: <span className="font-mono">{yLabel}</span>
              </span>
              <span className="font-medium">
                X: <span className="font-mono">{xLabel}</span>
              </span>
            </div>

            {/* Color legend */}
            <div className="mt-2 flex items-center gap-2">
              <span className="text-[10px] font-mono text-muted-foreground">
                {minVal.toFixed(2)}
              </span>
              <div
                className="flex-1 h-2.5 rounded-full overflow-hidden"
                style={{
                  background:
                    "linear-gradient(90deg, rgba(239,68,68,0.75), rgba(250,204,21,0.75), rgba(34,197,94,0.75))",
                }}
              />
              <span className="text-[10px] font-mono text-muted-foreground">
                {maxVal.toFixed(2)}
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Right Sidebar: Results ─────────────────────────────────────── */}
      <div className="space-y-3">
        {/* Best Configuration */}
        {sweepResult && (
          <div className="app-panel p-3 space-y-2">
            <div className="app-label flex items-center gap-1.5">
              <Trophy className="h-3 w-3 text-amber-400" />
              Best Configuration
            </div>

            {/* Param values */}
            <div className="space-y-1">
              {Object.entries(sweepResult.best_params).map(([key, val]) => (
                <div
                  key={key}
                  className="flex items-center justify-between text-xs"
                >
                  <span className="text-muted-foreground truncate mr-2">
                    {key}
                  </span>
                  <span className="font-mono font-medium">{val}</span>
                </div>
              ))}
            </div>

            {/* Main metric */}
            <div className="rounded-lg border border-emerald-400/20 bg-emerald-400/5 p-2.5 text-center">
              <div className="text-[10px] text-muted-foreground uppercase tracking-wider">
                {METRIC_OPTIONS.find((m) => m.value === metric)?.label ??
                  "Metric"}
              </div>
              <div className="text-xl font-mono font-bold text-emerald-400 mt-0.5">
                {sweepResult.best_value.toFixed(3)}
              </div>
            </div>

            {/* Secondary metrics */}
            {bestDataPoint?.metrics && (
              <div className="grid grid-cols-2 gap-1.5">
                {bestDataPoint.metrics.total_return != null && (
                  <div className="rounded-md border border-border/40 bg-muted/20 p-1.5 text-center">
                    <div className="text-[9px] text-muted-foreground uppercase">
                      Return
                    </div>
                    <div className="text-xs font-mono font-medium">
                      {(bestDataPoint.metrics.total_return * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
                {bestDataPoint.metrics.max_drawdown != null && (
                  <div className="rounded-md border border-border/40 bg-muted/20 p-1.5 text-center">
                    <div className="text-[9px] text-muted-foreground uppercase">
                      Max DD
                    </div>
                    <div className="text-xs font-mono font-medium text-red-300">
                      {(bestDataPoint.metrics.max_drawdown * 100).toFixed(1)}%
                    </div>
                  </div>
                )}
                {bestDataPoint.metrics.win_rate != null && (
                  <div className="rounded-md border border-border/40 bg-muted/20 p-1.5 text-center">
                    <div className="text-[9px] text-muted-foreground uppercase">
                      Win Rate
                    </div>
                    <div className="text-xs font-mono font-medium">
                      {(bestDataPoint.metrics.win_rate * 100).toFixed(0)}%
                    </div>
                  </div>
                )}
                {bestDataPoint.metrics.profit_factor != null && (
                  <div className="rounded-md border border-border/40 bg-muted/20 p-1.5 text-center">
                    <div className="text-[9px] text-muted-foreground uppercase">
                      P. Factor
                    </div>
                    <div className="text-xs font-mono font-medium">
                      {bestDataPoint.metrics.profit_factor.toFixed(2)}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Mini equity curve sparkline */}
            {bestDataPoint?.metrics?.equity_curve &&
              bestDataPoint.metrics.equity_curve.length > 1 && (
                <div className="rounded-md border border-border/40 bg-muted/10 p-2">
                  <div className="text-[9px] text-muted-foreground uppercase mb-1">
                    Equity Curve
                  </div>
                  <Sparkline data={bestDataPoint.metrics.equity_curve} />
                </div>
              )}

            {/* Apply button */}
            <Button variant="secondary" size="sm" className="w-full" disabled>
              <ArrowRight className="h-3 w-3" />
              Apply to Strategy
            </Button>
          </div>
        )}

        {/* Top 5 Combos */}
        {sweepResult && top5.length > 0 && (
          <div className="app-panel p-3 space-y-2">
            <div className="app-label">Top 5 Combos</div>
            <div className="space-y-1.5">
              {top5.map((dp, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-md border border-border/40 bg-muted/10 px-2 py-1.5"
                >
                  <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-muted/40 text-[10px] font-bold text-muted-foreground">
                    {i + 1}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-[10px] text-muted-foreground truncate font-mono">
                      {Object.entries(dp.params)
                        .map(([k, v]) => `${k}=${v}`)
                        .join(", ")}
                    </div>
                  </div>
                  <div className="text-xs font-mono font-semibold text-emerald-400 shrink-0">
                    {dp.value.toFixed(3)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state when no results */}
        {!sweepResult && (
          <div className="app-panel p-3">
            <div className="flex flex-col items-center gap-2 py-6 text-muted-foreground">
              <Trophy className="h-8 w-8 opacity-20" />
              <div className="text-xs text-center">
                Results will appear here after running a sweep
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
