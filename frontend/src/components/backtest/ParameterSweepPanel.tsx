"use client";

import React, { useState, useMemo, useCallback, useEffect, useRef } from "react";
import {
  Grid3X3,
  Trophy,
  ChevronDown,
  Zap,
  Copy,
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

// ── HSL color interpolation (red → yellow → green, no muddy browns) ─────

function metricColorHSL(value: number, min: number, max: number): string {
  if (max === min) return "hsla(45, 90%, 55%, 0.75)";
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  // Red = hsl(0,70%,45%), Yellow = hsl(45,90%,55%), Green = hsl(145,65%,45%)
  let h: number, s: number, l: number;
  if (t < 0.5) {
    const u = t * 2;
    h = 0 + (45 - 0) * u;
    s = 70 + (90 - 70) * u;
    l = 45 + (55 - 45) * u;
  } else {
    const u = (t - 0.5) * 2;
    h = 45 + (145 - 45) * u;
    s = 90 + (65 - 90) * u;
    l = 55 + (45 - 55) * u;
  }
  return `hsla(${h.toFixed(1)}, ${s.toFixed(1)}%, ${l.toFixed(1)}%, 0.80)`;
}

function metricTextColor(value: number, min: number, max: number): string {
  if (max === min) return "rgba(0,0,0,0.85)";
  const t = Math.max(0, Math.min(1, (value - min) / (max - min)));
  if (t > 0.28 && t < 0.72) return "rgba(0,0,0,0.85)";
  return "rgba(255,255,255,0.92)";
}

// ── Animated sparkline SVG (draws on mount) ─────────────────────────────

function Sparkline({ data }: { data: { date: string; value: number }[] }) {
  const pathRef = useRef<SVGPolylineElement>(null);
  const [drawn, setDrawn] = useState(false);

  useEffect(() => {
    const el = pathRef.current;
    if (!el) return;
    const len = el.getTotalLength?.() ?? 200;
    el.style.strokeDasharray = `${len}`;
    el.style.strokeDashoffset = `${len}`;
    // trigger reflow then animate
    void el.getBoundingClientRect();
    el.style.transition = "stroke-dashoffset 900ms cubic-bezier(0.4,0,0.2,1)";
    el.style.strokeDashoffset = "0";
    setDrawn(true);
  }, [data]);

  if (!data || data.length < 2) return null;
  const values = data.map((d) => d.value);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 128;
  const h = 36;
  const points = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / range) * (h - 4) - 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  const isPositive = values[values.length - 1] >= values[0];
  return (
    <svg width={w} height={h} className="block">
      {/* gradient fill area */}
      <defs>
        <linearGradient id="spark-fill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity="0.18" />
          <stop offset="100%" stopColor={isPositive ? "#22c55e" : "#ef4444"} stopOpacity="0" />
        </linearGradient>
      </defs>
      <polyline
        ref={pathRef}
        fill="none"
        stroke={isPositive ? "#22c55e" : "#ef4444"}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        style={{ opacity: drawn ? 1 : 1 }}
      />
    </svg>
  );
}

// ── Loading shimmer grid ─────────────────────────────────────────────────

function SweepLoadingGrid({
  totalCombinations,
}: {
  totalCombinations: number;
}) {
  const cols = 7;
  const rows = 5;
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-4 px-4">
      <div className="space-y-1">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-1">
            {Array.from({ length: cols }).map((_, c) => {
              const delay = (r * cols + c) * 60;
              return (
                <div
                  key={c}
                  className="h-8 w-8 rounded-sm"
                  style={{
                    background:
                      "linear-gradient(90deg, hsl(var(--surface-3)/0.8) 0%, hsl(var(--surface-2)/1) 50%, hsl(var(--surface-3)/0.8) 100%)",
                    backgroundSize: "240px 100%",
                    animation: `app-shimmer 1.4s linear ${delay}ms infinite`,
                    borderRadius: "4px",
                  }}
                />
              );
            })}
          </div>
        ))}
      </div>
      <div className="text-center space-y-1">
        <div className="text-sm font-medium text-foreground">
          Testing {totalCombinations.toLocaleString()} combinations...
        </div>
        <div className="text-xs text-muted-foreground">
          This may take a minute
        </div>
        {/* Progress bar */}
        <div className="w-48 h-1 rounded-full bg-muted/40 overflow-hidden mt-2">
          <div
            className="h-full rounded-full"
            style={{
              background: "linear-gradient(90deg, hsl(var(--primary)), hsl(var(--info)))",
              animation: "sweep-progress 2s ease-in-out infinite alternate",
              width: "60%",
            }}
          />
        </div>
      </div>
    </div>
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

// ── Rank badge colors ────────────────────────────────────────────────────

function RankBadge({ rank }: { rank: number }) {
  const styles: Record<number, { bg: string; text: string; shadow?: string }> = {
    1: { bg: "linear-gradient(135deg, #f59e0b, #d97706)", text: "#fff", shadow: "0 2px 8px rgba(245,158,11,0.45)" },
    2: { bg: "linear-gradient(135deg, #94a3b8, #64748b)", text: "#fff", shadow: "0 2px 6px rgba(148,163,184,0.35)" },
    3: { bg: "linear-gradient(135deg, #cd7c3a, #a0522d)", text: "#fff", shadow: "0 2px 6px rgba(160,82,45,0.35)" },
  };
  const s = styles[rank] ?? { bg: "hsl(var(--muted)/0.5)", text: "hsl(var(--muted-foreground))" };
  return (
    <div
      className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[10px] font-bold"
      style={{ background: s.bg, color: s.text, boxShadow: s.shadow }}
    >
      {rank}
    </div>
  );
}

// ── Heatmap cell tooltip ─────────────────────────────────────────────────

interface CellTooltipProps {
  xLabel: string;
  yLabel: string;
  xVal: number;
  yVal: number;
  value: number;
  metric: string;
}

function CellTooltip({ xLabel, yLabel, xVal, yVal, value, metric }: CellTooltipProps) {
  return (
    <div
      className="pointer-events-none absolute -top-14 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-[10px] font-mono shadow-lg"
      style={{
        background: "hsl(var(--card))",
        borderColor: "hsl(var(--border)/0.8)",
        boxShadow: "var(--shadow-2)",
      }}
    >
      <div className="font-semibold text-foreground mb-0.5">{metric}: {value.toFixed(3)}</div>
      <div className="text-muted-foreground">
        {xLabel}={xVal} · {yLabel}={yVal}
      </div>
      {/* Arrow */}
      <div
        className="absolute left-1/2 -bottom-1 -translate-x-1/2 h-2 w-2 rotate-45 border-b border-r"
        style={{ background: "hsl(var(--card))", borderColor: "hsl(var(--border)/0.8)" }}
      />
    </div>
  );
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
  const defaultRanges = useMemo(() => extractParamRanges(strategy), [strategy]);

  const [paramRanges, setParamRanges] = useState<ParamRange[]>(() =>
    defaultRanges.length >= 2 ? defaultRanges.slice(0, 2) : defaultRanges
  );
  const [metric, setMetric] = useState<OptimizeMetric>("sharpe");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sweepResult, setSweepResult] = useState<SweepResult | null>(null);
  const [hoveredCell, setHoveredCell] = useState<{ row: number; col: number } | null>(null);
  const [resultsVisible, setResultsVisible] = useState(false);

  // Fade in results when they arrive
  useEffect(() => {
    if (sweepResult) {
      const t = setTimeout(() => setResultsVisible(true), 50);
      return () => clearTimeout(t);
    } else {
      setResultsVisible(false);
    }
  }, [sweepResult]);

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
    setResultsVisible(false);
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
  }, [strategy, symbol, lookbackDays, parameterRangesPayload, metric]);

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

    const sorted = [...sweepResult.heatmap_data].sort((a, b) => b.value - a.value);
    const top5 = sorted.slice(0, 5);

    return { xAxis, yAxis, xLabel, yLabel, matrix: mat, minVal, maxVal, bestRow, bestCol, top5 };
  }, [sweepResult]);

  const bestDataPoint = useMemo(() => {
    if (!sweepResult) return null;
    return (
      sweepResult.heatmap_data.find((d) => {
        const bp = sweepResult.best_params;
        return Object.keys(bp).every((k) => d.params[k] === bp[k]);
      }) ?? null
    );
  }, [sweepResult]);

  const metricLabel = METRIC_OPTIONS.find((m) => m.value === metric)?.label ?? "Metric";

  return (
    <>
      {/* Keyframe injection — only needed once per page but safe to repeat */}
      <style>{`
        @keyframes sweep-progress {
          from { width: 15%; }
          to   { width: 85%; }
        }
        @keyframes best-cell-pulse {
          0%, 100% { box-shadow: 0 0 0 2px rgba(245,158,11,0.55), 0 0 14px rgba(245,158,11,0.30); }
          50%       { box-shadow: 0 0 0 2px rgba(245,158,11,0.20), 0 0 6px  rgba(245,158,11,0.10); }
        }
        @keyframes row-appear {
          from { opacity: 0; transform: translateY(4px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes fade-in-up {
          from { opacity: 0; transform: translateY(8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
      `}</style>

      {/* 3-column layout; stacks vertically below lg breakpoint */}
      <div className="grid grid-cols-1 gap-3 lg:grid-cols-[240px_1fr_260px]">

        {/* ── Left: Sweep Config ─────────────────────────────────────── */}
        <div className="space-y-3">
          {/* Strategy info */}
          <div className="app-panel p-3">
            <div className="app-label mb-1.5">Strategy</div>
            <div className="text-sm font-medium truncate">{strategy.name}</div>
            <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
              <span className="font-mono">{symbol}</span>
              <span className="opacity-40">·</span>
              <span className="font-mono">{strategy.timeframe || "1D"}</span>
            </div>
          </div>

          {/* Parameter ranges */}
          <div className="app-panel p-3 space-y-4">
            <div className="app-label">Parameter Ranges</div>
            {paramRanges.length === 0 && (
              <div className="text-xs text-muted-foreground">
                No tuneable parameters detected in this strategy.
              </div>
            )}
            {paramRanges.map((pr, i) => (
              <div key={pr.name} className="space-y-2">
                <div className="text-[11px] font-medium text-foreground/80 truncate">
                  {pr.label}
                </div>

                {/* Three number inputs */}
                <div className="grid grid-cols-3 gap-1.5">
                  {(["min", "max", "step"] as const).map((field) => (
                    <div key={field}>
                      <label className="text-[10px] text-muted-foreground/70 font-mono uppercase tracking-wide">
                        {field}
                      </label>
                      <input
                        type="number"
                        value={pr[field]}
                        onChange={(e) =>
                          updateRange(
                            i,
                            field,
                            field === "step"
                              ? Math.max(1, parseFloat(e.target.value) || 1)
                              : parseFloat(e.target.value) || 1
                          )
                        }
                        className="mt-0.5 w-full rounded-md border bg-card px-2 py-1 text-[11px] font-mono text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
                        style={{ borderColor: "hsl(var(--border)/0.6)" }}
                      />
                    </div>
                  ))}
                </div>

                {/* Range track with live value display */}
                <div>
                  <input
                    type="range"
                    min={pr.min}
                    max={pr.max}
                    step={pr.step}
                    defaultValue={Math.round((pr.min + pr.max) / 2)}
                    className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                    style={{ accentColor: "hsl(var(--primary))" }}
                  />
                  <div className="flex justify-between text-[10px] text-muted-foreground font-mono mt-0.5">
                    <span>{pr.min}</span>
                    <span className="text-primary/70">
                      {Math.round((pr.max - pr.min) / pr.step) + 1} steps
                    </span>
                    <span>{pr.max}</span>
                  </div>
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
                className="w-full appearance-none rounded-md border bg-card px-2 py-1.5 pr-7 text-xs text-foreground focus:outline-none focus:ring-1 focus:ring-ring/50"
                style={{ borderColor: "hsl(var(--border)/0.6)" }}
              >
                {METRIC_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 h-3 w-3 text-muted-foreground" />
            </div>
            <div className="text-[10px] text-muted-foreground font-mono tabular-nums">
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
              <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="3" strokeOpacity="0.25" />
                <path d="M12 2 A10 10 0 0 1 22 12" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
              </svg>
            ) : (
              <Zap className="h-3.5 w-3.5" />
            )}
            {running ? "Sweeping..." : "Run Sweep"}
          </Button>

          {error && (
            <div className="rounded-md border border-red-400/20 bg-red-400/5 px-3 py-2 text-xs text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* ── Center: Heatmap ────────────────────────────────────────── */}
        <div className="app-panel p-3 min-h-[420px] flex flex-col">

          {/* Empty state */}
          {!sweepResult && !running && (
            <div className="flex-1 flex flex-col items-center justify-center gap-4 text-muted-foreground">
              <div
                className="flex h-16 w-16 items-center justify-center rounded-2xl border"
                style={{
                  borderColor: "hsl(var(--border)/0.6)",
                  background: "hsl(var(--surface-3)/0.6)",
                }}
              >
                <Grid3X3 className="h-7 w-7 opacity-40" />
              </div>
              <div className="text-center space-y-1">
                <div className="text-sm font-medium text-foreground/70">
                  Configure parameters and run a sweep
                </div>
                <div className="text-xs text-muted-foreground/70">
                  The heatmap will appear here once complete
                </div>
              </div>
              {/* Decorative mini grid */}
              <div className="flex gap-1 opacity-20">
                {Array.from({ length: 5 }).map((_, r) => (
                  <div key={r} className="flex flex-col gap-1">
                    {Array.from({ length: 4 }).map((_, c) => (
                      <div
                        key={c}
                        className="h-4 w-4 rounded-sm"
                        style={{
                          background: `hsl(${(r * 4 + c) * 12}, 50%, 50%)`,
                          opacity: 0.4 + (r * 4 + c) * 0.04,
                        }}
                      />
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Loading state */}
          {running && <SweepLoadingGrid totalCombinations={totalCombinations} />}

          {/* Heatmap results */}
          {sweepResult && matrix.length > 0 && (
            <div
              className="flex-1 flex flex-col"
              style={{
                opacity: resultsVisible ? 1 : 0,
                transform: resultsVisible ? "translateY(0)" : "translateY(6px)",
                transition: "opacity 400ms ease, transform 400ms ease",
              }}
            >
              <div className="app-label mb-3 flex items-center gap-2">
                <Grid3X3 className="h-3.5 w-3.5" />
                Parameter Sweep Heatmap
              </div>

              <div className="flex-1 overflow-auto">
                <div className="inline-block min-w-full">
                  {/* X-axis column headers */}
                  <div className="flex mb-0.5">
                    <div className="w-14 shrink-0" />
                    {xAxis.map((xVal) => (
                      <div
                        key={xVal}
                        className="flex-1 min-w-[44px] text-center text-[10px] text-muted-foreground font-mono pb-1"
                      >
                        {xVal}
                      </div>
                    ))}
                  </div>

                  {/* Grid rows with staggered reveal */}
                  {yAxis.map((yVal, rowIdx) => (
                    <div
                      key={yVal}
                      className="flex"
                      style={{
                        animation: `row-appear 300ms ease-out ${rowIdx * 40}ms both`,
                      }}
                    >
                      {/* Y-axis label */}
                      <div className="w-14 shrink-0 flex items-center justify-end pr-2 text-[10px] text-muted-foreground font-mono">
                        {yVal}
                      </div>

                      {/* Cells */}
                      {xAxis.map((xVal, colIdx) => {
                        const val = matrix[rowIdx]?.[colIdx] ?? NaN;
                        const isNanVal = isNaN(val);
                        const isBest = rowIdx === bestRow && colIdx === bestCol;
                        const isHovered =
                          hoveredCell?.row === rowIdx && hoveredCell?.col === colIdx;

                        return (
                          <div
                            key={colIdx}
                            className="relative flex-1 min-w-[44px] aspect-square flex items-center justify-center text-[11px] font-mono font-medium cursor-default"
                            style={{
                              backgroundColor: isNanVal
                                ? "rgba(100,100,100,0.12)"
                                : metricColorHSL(val, minVal, maxVal),
                              color: isNanVal
                                ? "rgba(100,100,100,0.4)"
                                : metricTextColor(val, minVal, maxVal),
                              borderRadius: "4px",
                              margin: "1px",
                              border: isBest
                                ? "2px solid rgba(245,158,11,0.8)"
                                : isHovered
                                ? "1px solid rgba(255,255,255,0.35)"
                                : "1px solid rgba(255,255,255,0.06)",
                              transform: isHovered ? "scale(1.1)" : "scale(1)",
                              zIndex: isHovered ? 10 : 1,
                              animation: isBest
                                ? "best-cell-pulse 2s ease-in-out infinite"
                                : undefined,
                              transition:
                                "transform 150ms cubic-bezier(0.34,1.56,0.64,1), border-color 150ms ease",
                            }}
                            onMouseEnter={() =>
                              setHoveredCell({ row: rowIdx, col: colIdx })
                            }
                            onMouseLeave={() => setHoveredCell(null)}
                          >
                            {isNanVal ? (
                              <span className="opacity-30">–</span>
                            ) : (
                              val.toFixed(2)
                            )}

                            {/* Tooltip on hover */}
                            {isHovered && !isNanVal && (
                              <CellTooltip
                                xLabel={xLabel}
                                yLabel={yLabel}
                                xVal={xVal}
                                yVal={yVal}
                                value={val}
                                metric={metricLabel}
                              />
                            )}
                          </div>
                        );
                      })}
                    </div>
                  ))}
                </div>
              </div>

              {/* Axis labels */}
              <div className="mt-2.5 flex items-center justify-between text-[10px] text-muted-foreground font-mono">
                <span>
                  Y: <span className="text-foreground/60">{yLabel}</span>
                </span>
                <span>
                  X: <span className="text-foreground/60">{xLabel}</span>
                </span>
              </div>

              {/* Color legend using HSL gradient */}
              <div className="mt-2 flex items-center gap-2">
                <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
                  {minVal.toFixed(2)}
                </span>
                <div
                  className="flex-1 h-2 rounded-full overflow-hidden"
                  style={{
                    background:
                      "linear-gradient(90deg, hsla(0,70%,45%,0.8), hsla(45,90%,55%,0.8), hsla(145,65%,45%,0.8))",
                  }}
                />
                <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
                  {maxVal.toFixed(2)}
                </span>
              </div>
            </div>
          )}
        </div>

        {/* ── Right: Results ─────────────────────────────────────────── */}
        <div className="space-y-3">

          {/* Best Configuration card */}
          {sweepResult && (
            <div
              className="app-panel p-3 space-y-3"
              style={{
                opacity: resultsVisible ? 1 : 0,
                transform: resultsVisible ? "translateY(0)" : "translateY(8px)",
                transition: "opacity 450ms ease 100ms, transform 450ms ease 100ms",
              }}
            >
              <div className="app-label flex items-center gap-1.5">
                <Trophy className="h-3 w-3 text-amber-400" />
                Best Configuration
              </div>

              {/* Param key/value pairs */}
              <div className="space-y-1">
                {Object.entries(sweepResult.best_params).map(([key, val]) => (
                  <div
                    key={key}
                    className="flex items-center justify-between text-xs"
                  >
                    <span className="text-muted-foreground truncate mr-2 font-mono">
                      {key}
                    </span>
                    <span className="font-mono font-semibold text-foreground">
                      {val}
                    </span>
                  </div>
                ))}
              </div>

              {/* Primary metric — large and prominent */}
              <div
                className="rounded-lg border p-3 text-center"
                style={{
                  borderColor: "hsl(var(--positive)/0.25)",
                  background: "hsl(var(--positive)/0.06)",
                }}
              >
                <div className="text-[10px] text-muted-foreground uppercase tracking-widest font-semibold">
                  {metricLabel}
                </div>
                <div
                  className="text-3xl font-mono font-bold mt-1 tabular-nums"
                  style={{ color: "hsl(var(--positive))" }}
                >
                  {sweepResult.best_value.toFixed(3)}
                </div>
              </div>

              {/* Secondary metrics grid */}
              {bestDataPoint?.metrics && (
                <div className="grid grid-cols-2 gap-1.5">
                  {bestDataPoint.metrics.total_return != null && (
                    <div
                      className="rounded-md border p-1.5 text-center"
                      style={{
                        borderColor: "hsl(var(--border)/0.4)",
                        background: "hsl(var(--muted)/0.2)",
                      }}
                    >
                      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Return</div>
                      <div className="text-xs font-mono font-semibold mt-0.5">
                        {(bestDataPoint.metrics.total_return * 100).toFixed(1)}%
                      </div>
                    </div>
                  )}
                  {bestDataPoint.metrics.max_drawdown != null && (
                    <div
                      className="rounded-md border p-1.5 text-center"
                      style={{
                        borderColor: "hsl(var(--border)/0.4)",
                        background: "hsl(var(--muted)/0.2)",
                      }}
                    >
                      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Max DD</div>
                      <div className="text-xs font-mono font-semibold mt-0.5 text-red-400">
                        {(bestDataPoint.metrics.max_drawdown * 100).toFixed(1)}%
                      </div>
                    </div>
                  )}
                  {bestDataPoint.metrics.win_rate != null && (
                    <div
                      className="rounded-md border p-1.5 text-center"
                      style={{
                        borderColor: "hsl(var(--border)/0.4)",
                        background: "hsl(var(--muted)/0.2)",
                      }}
                    >
                      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">Win Rate</div>
                      <div className="text-xs font-mono font-semibold mt-0.5">
                        {(bestDataPoint.metrics.win_rate * 100).toFixed(0)}%
                      </div>
                    </div>
                  )}
                  {bestDataPoint.metrics.profit_factor != null && (
                    <div
                      className="rounded-md border p-1.5 text-center"
                      style={{
                        borderColor: "hsl(var(--border)/0.4)",
                        background: "hsl(var(--muted)/0.2)",
                      }}
                    >
                      <div className="text-[9px] text-muted-foreground uppercase tracking-wider">P. Factor</div>
                      <div className="text-xs font-mono font-semibold mt-0.5">
                        {bestDataPoint.metrics.profit_factor.toFixed(2)}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Animated equity sparkline */}
              {bestDataPoint?.metrics?.equity_curve &&
                bestDataPoint.metrics.equity_curve.length > 1 && (
                  <div
                    className="rounded-md border p-2"
                    style={{
                      borderColor: "hsl(var(--border)/0.4)",
                      background: "hsl(var(--muted)/0.1)",
                    }}
                  >
                    <div className="text-[9px] text-muted-foreground uppercase tracking-wider mb-1.5">
                      Equity Curve
                    </div>
                    <Sparkline data={bestDataPoint.metrics.equity_curve} />
                  </div>
                )}

              {/* Copy best parameters to clipboard */}
              <button
                className="w-full flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-white"
                style={{
                  background: "linear-gradient(135deg, hsl(var(--primary)), hsl(var(--info)))",
                  boxShadow: "0 4px 14px -4px hsl(var(--primary)/0.45)",
                }}
                onClick={() => {
                  const params = sweepResult?.best_params;
                  if (params) {
                    const text = JSON.stringify(params, null, 2);
                    navigator.clipboard.writeText(text).catch(() => {});
                  }
                }}
              >
                <Copy className="h-3.5 w-3.5" />
                Copy Parameters
              </button>
            </div>
          )}

          {/* Top 5 combos */}
          {sweepResult && top5.length > 0 && (
            <div
              className="app-panel p-3 space-y-2"
              style={{
                opacity: resultsVisible ? 1 : 0,
                transform: resultsVisible ? "translateY(0)" : "translateY(8px)",
                transition: "opacity 450ms ease 200ms, transform 450ms ease 200ms",
              }}
            >
              <div className="app-label">Top 5 Combos</div>
              <div className="space-y-1">
                {top5.map((dp, i) => (
                  <div
                    key={i}
                    className="group flex items-center gap-2 rounded-md border px-2 py-1.5 transition-colors cursor-default"
                    style={{
                      borderColor: "hsl(var(--border)/0.4)",
                      background: "hsl(var(--muted)/0.08)",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLElement).style.background =
                        "hsl(var(--muted)/0.25)";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLElement).style.background =
                        "hsl(var(--muted)/0.08)";
                    }}
                  >
                    <RankBadge rank={i + 1} />
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-muted-foreground truncate font-mono">
                        {Object.entries(dp.params)
                          .map(([k, v]) => `${k}=${v}`)
                          .join(", ")}
                      </div>
                    </div>
                    <div
                      className="text-xs font-mono font-semibold shrink-0 tabular-nums"
                      style={{ color: "hsl(var(--positive))" }}
                    >
                      {dp.value.toFixed(3)}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Right-panel empty state */}
          {!sweepResult && (
            <div className="app-panel p-3">
              <div className="flex flex-col items-center gap-3 py-8 text-muted-foreground">
                <Trophy className="h-9 w-9 opacity-15" />
                <div className="text-xs text-center leading-relaxed">
                  Top results will appear here<br />after running a sweep
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </>
  );
}
