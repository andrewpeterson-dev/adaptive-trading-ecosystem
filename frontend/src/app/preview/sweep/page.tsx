"use client";

import React, { useState } from "react";
import { Grid3X3, Sliders, Trophy, TrendingUp, Target, Zap } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts";
import { Surface, SurfaceHeader, SurfaceBody, SurfaceTitle } from "@/components/ui/surface";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { PageHeader } from "@/components/layout/PageHeader";

// ---------------------------------------------------------------------------
// Mock data — all hardcoded, no API calls
// ---------------------------------------------------------------------------

const RSI_PERIODS = [10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30];
const SMA_PERIODS = [20, 30, 40, 50, 60, 70, 80, 90, 100];

// Generate a realistic Sharpe surface: peak ~1.82 at RSI=14, SMA=50
function generateHeatmapData() {
  const data: Record<string, number> = {};
  for (const rsi of RSI_PERIODS) {
    for (const sma of SMA_PERIODS) {
      // Distance from optimal (RSI=14, SMA=50)
      const rsiDist = Math.abs(rsi - 14) / 20;
      const smaDist = Math.abs(sma - 50) / 80;
      const dist = Math.sqrt(rsiDist ** 2 + smaDist ** 2);
      // Decay from peak, with small random noise
      const seed = ((rsi * 7 + sma * 3) % 17) / 17; // deterministic noise
      const noise = (seed - 0.5) * 0.18;
      const sharpe = 1.82 * Math.exp(-2.4 * dist) - 0.05 + noise;
      data[`${rsi}_${sma}`] = Math.round(sharpe * 100) / 100;
    }
  }
  return data;
}

const HEATMAP = generateHeatmapData();

// Top 5 combinations by Sharpe
const TOP_COMBOS = [
  { rank: 1, rsi: 14, sma: 50, sharpe: 1.82, ret: 24.7, dd: -8.3, wr: 63 },
  { rank: 2, rsi: 12, sma: 50, sharpe: 1.61, ret: 21.4, dd: -9.1, wr: 61 },
  { rank: 3, rsi: 14, sma: 40, sharpe: 1.54, ret: 20.8, dd: -10.2, wr: 60 },
  { rank: 4, rsi: 16, sma: 50, sharpe: 1.47, ret: 19.6, dd: -9.7, wr: 59 },
  { rank: 5, rsi: 14, sma: 60, sharpe: 1.39, ret: 18.9, dd: -11.4, wr: 58 },
];

// Equity sparkline data — 36 weeks of mock growth with mild drawdown
const SPARKLINE = (() => {
  const points = [];
  let val = 100000;
  for (let i = 0; i <= 36; i++) {
    const seed = (i * 13 + 7) % 29;
    const change = (seed / 29 - 0.38) * 2200;
    val = Math.max(val + change, 95000);
    points.push({ w: i, v: Math.round(val) });
  }
  // Ensure it ends higher
  points[36].v = 124700;
  return points;
})();

// ---------------------------------------------------------------------------
// Color scale helpers
// ---------------------------------------------------------------------------

function sharpeToColor(sharpe: number): string {
  if (sharpe < -0.1) return "rgb(185,28,28)";       // red-700
  if (sharpe < 0.2)  return "rgb(220,38,38)";       // red-600
  if (sharpe < 0.5)  return "rgb(234,88,12)";       // orange-600
  if (sharpe < 0.8)  return "rgb(202,138,4)";       // yellow-600
  if (sharpe < 1.1)  return "rgb(101,163,13)";      // lime-600
  if (sharpe < 1.4)  return "rgb(22,163,74)";       // green-600
  if (sharpe < 1.65) return "rgb(5,150,105)";       // emerald-600
  return "rgb(4,120,87)";                            // emerald-700 (brightest)
}

function sharpeToBg(sharpe: number): string {
  if (sharpe < -0.1) return "rgba(185,28,28,0.35)";
  if (sharpe < 0.2)  return "rgba(220,38,38,0.28)";
  if (sharpe < 0.5)  return "rgba(234,88,12,0.28)";
  if (sharpe < 0.8)  return "rgba(202,138,4,0.28)";
  if (sharpe < 1.1)  return "rgba(101,163,13,0.28)";
  if (sharpe < 1.4)  return "rgba(22,163,74,0.30)";
  if (sharpe < 1.65) return "rgba(5,150,105,0.35)";
  return "rgba(4,120,87,0.42)";
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function SliderRow({
  label,
  min,
  max,
  rangeMin,
  rangeMax,
  unit = "",
}: {
  label: string;
  min: number;
  max: number;
  rangeMin: number;
  rangeMax: number;
  unit?: string;
}) {
  const total = max - min;
  const leftPct = ((rangeMin - min) / total) * 100;
  const widthPct = ((rangeMax - rangeMin) / total) * 100;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-xs">
        <span className="font-medium text-foreground">{label}</span>
        <span className="font-mono text-muted-foreground">
          {rangeMin}{unit} – {rangeMax}{unit}
        </span>
      </div>
      <div className="relative h-2 rounded-full bg-muted/60">
        {/* Track range highlight */}
        <div
          className="absolute top-0 h-2 rounded-full bg-primary/60"
          style={{ left: `${leftPct}%`, width: `${widthPct}%` }}
        />
        {/* Min thumb */}
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-primary bg-card shadow"
          style={{ left: `${leftPct}%` }}
        />
        {/* Max thumb */}
        <div
          className="absolute top-1/2 h-3.5 w-3.5 -translate-y-1/2 -translate-x-1/2 rounded-full border-2 border-primary bg-card shadow"
          style={{ left: `${leftPct + widthPct}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground/60">
        <span>{min}{unit}</span>
        <span>{max}{unit}</span>
      </div>
    </div>
  );
}

function HeatmapGrid() {
  return (
    <div className="space-y-3">
      {/* Y-axis label */}
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
          SMA Period (Y) / RSI Period (X)
        </span>
      </div>

      <div className="overflow-x-auto">
        <div style={{ minWidth: 520 }}>
          {/* Column headers (RSI periods) */}
          <div className="mb-1 ml-10 grid" style={{ gridTemplateColumns: `repeat(${RSI_PERIODS.length}, 1fr)` }}>
            {RSI_PERIODS.map((rsi) => (
              <div key={rsi} className="text-center text-[10px] font-mono text-muted-foreground">
                {rsi}
              </div>
            ))}
          </div>

          {/* Rows (SMA periods, reversed so higher SMA is at top) */}
          {[...SMA_PERIODS].reverse().map((sma) => (
            <div key={sma} className="mb-0.5 flex items-center gap-1">
              {/* Row header */}
              <div className="w-9 flex-shrink-0 text-right text-[10px] font-mono text-muted-foreground">
                {sma}
              </div>
              {/* Cells */}
              <div className="grid flex-1 gap-0.5" style={{ gridTemplateColumns: `repeat(${RSI_PERIODS.length}, 1fr)` }}>
                {RSI_PERIODS.map((rsi) => {
                  const sharpe = HEATMAP[`${rsi}_${sma}`];
                  const isBest = rsi === 14 && sma === 50;
                  return (
                    <div
                      key={rsi}
                      title={`RSI ${rsi}, SMA ${sma} → Sharpe ${sharpe.toFixed(2)}`}
                      style={{
                        backgroundColor: sharpeToBg(sharpe),
                        border: isBest ? "2px solid #f59e0b" : "1px solid transparent",
                        boxShadow: isBest ? "0 0 0 1px rgba(245,158,11,0.3)" : undefined,
                      }}
                      className="relative flex aspect-square items-center justify-center rounded-sm transition-all hover:z-10 hover:scale-110 hover:shadow-lg"
                    >
                      <span
                        className="text-[9px] font-mono font-semibold leading-none"
                        style={{ color: sharpeToColor(sharpe) }}
                      >
                        {sharpe.toFixed(2)}
                      </span>
                      {isBest && (
                        <span className="absolute -right-0.5 -top-0.5 text-[8px]">★</span>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Color scale legend */}
      <div className="mt-4 flex items-center gap-3">
        <span className="text-[10px] text-muted-foreground">Sharpe:</span>
        <div className="flex flex-1 overflow-hidden rounded-full" style={{ height: 8 }}>
          {[
            "rgba(185,28,28,0.6)",
            "rgba(220,38,38,0.55)",
            "rgba(234,88,12,0.55)",
            "rgba(202,138,4,0.55)",
            "rgba(101,163,13,0.55)",
            "rgba(22,163,74,0.6)",
            "rgba(5,150,105,0.65)",
            "rgba(4,120,87,0.72)",
          ].map((c, i) => (
            <div key={i} className="flex-1" style={{ backgroundColor: c }} />
          ))}
        </div>
        <div className="flex justify-between text-[10px] font-mono text-muted-foreground" style={{ width: 80 }}>
          <span>-0.3</span>
          <span>1.8</span>
        </div>
      </div>
    </div>
  );
}

function SparklineChart() {
  return (
    <ResponsiveContainer width="100%" height={64}>
      <AreaChart data={SPARKLINE} margin={{ top: 4, right: 0, bottom: 0, left: 0 }}>
        <defs>
          <linearGradient id="sparkGrad" x1="0" y1="0" x2="0" y2="1">
            <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
            <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="v"
          stroke="#10b981"
          strokeWidth={1.5}
          fill="url(#sparkGrad)"
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          contentStyle={{ display: "none" }}
          cursor={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

function BestMetricRow({
  label,
  value,
  color = "text-foreground",
}: {
  label: string;
  value: string;
  color?: string;
}) {
  return (
    <div className="flex items-center justify-between py-2">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className={`font-mono text-sm font-semibold ${color}`}>{value}</span>
    </div>
  );
}

function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) return <span className="text-amber-400 text-xs font-bold">#{rank}</span>;
  if (rank === 2) return <span className="text-slate-300 text-xs font-bold">#{rank}</span>;
  if (rank === 3) return <span className="text-amber-700 text-xs font-bold">#{rank}</span>;
  return <span className="text-xs text-muted-foreground font-mono">#{rank}</span>;
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function SweepPreviewPage() {
  // Non-functional UI state — just for visual realism
  const [selectedMetric] = useState("Sharpe Ratio");

  return (
    <div className="flex flex-col gap-6 p-6">
      {/* Page Header */}
      <PageHeader
        eyebrow="Backtesting"
        title="Parameter Sweep"
        description="Explore how strategy performance varies across a grid of parameter combinations."
        badge={
          <Badge variant="info">
            <Grid3X3 className="h-3 w-3" />
            Preview
          </Badge>
        }
      />

      {/* Three-column layout */}
      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[280px_1fr_280px]">

        {/* ---------------------------------------------------------------- */}
        {/* LEFT — Sweep Configuration                                        */}
        {/* ---------------------------------------------------------------- */}
        <Surface className="h-fit">
          <SurfaceHeader>
            <div className="flex items-center gap-2">
              <Sliders className="h-4 w-4 text-primary" />
              <SurfaceTitle>Sweep Config</SurfaceTitle>
            </div>
          </SurfaceHeader>
          <SurfaceBody className="space-y-5">

            {/* Strategy name */}
            <div className="space-y-1">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Strategy
              </p>
              <p className="text-sm font-semibold text-foreground">RSI Mean Reversion</p>
            </div>

            {/* Symbol / Timeframe */}
            <div className="grid grid-cols-2 gap-3">
              <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Symbol</p>
                <p className="mt-0.5 font-mono text-sm font-semibold">SPY</p>
              </div>
              <div className="rounded-lg border border-border/60 bg-muted/30 px-3 py-2">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">Timeframe</p>
                <p className="mt-0.5 font-mono text-sm font-semibold">1D</p>
              </div>
            </div>

            {/* Parameter ranges */}
            <div className="space-y-4">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Parameter Ranges
              </p>
              <SliderRow label="RSI Period" min={5} max={35} rangeMin={10} rangeMax={30} />
              <SliderRow label="SMA Period" min={10} max={120} rangeMin={20} rangeMax={100} />
            </div>

            {/* Metric selector */}
            <div className="space-y-1.5">
              <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                Optimize For
              </p>
              <div className="flex items-center justify-between rounded-lg border border-border/60 bg-muted/30 px-3 py-2.5">
                <div className="flex items-center gap-2">
                  <Target className="h-3.5 w-3.5 text-primary" />
                  <span className="text-sm font-medium">{selectedMetric}</span>
                </div>
                <svg className="h-4 w-4 text-muted-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>

            {/* Combo count + run button */}
            <div className="space-y-3 pt-1">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <div className="flex items-center gap-1.5">
                  <Zap className="h-3 w-3" />
                  <span>Combinations</span>
                </div>
                <span className="font-mono font-semibold text-foreground">234</span>
              </div>
              <Button variant="primary" size="md" className="w-full">
                <TrendingUp className="h-4 w-4" />
                Run Sweep
              </Button>
            </div>

          </SurfaceBody>
        </Surface>

        {/* ---------------------------------------------------------------- */}
        {/* CENTER — Heatmap                                                  */}
        {/* ---------------------------------------------------------------- */}
        <Surface>
          <SurfaceHeader>
            <div className="flex items-center gap-2">
              <Grid3X3 className="h-4 w-4 text-primary" />
              <SurfaceTitle>Sharpe Ratio Heatmap</SurfaceTitle>
            </div>
            <div className="ml-auto flex items-center gap-2">
              <Badge variant="warning">
                <span className="text-[10px]">★ Best at RSI 14, SMA 50</span>
              </Badge>
            </div>
          </SurfaceHeader>
          <SurfaceBody>
            <HeatmapGrid />
          </SurfaceBody>
        </Surface>

        {/* ---------------------------------------------------------------- */}
        {/* RIGHT — Best Parameters                                           */}
        {/* ---------------------------------------------------------------- */}
        <div className="flex flex-col gap-5">

          {/* Best config card */}
          <div className="rounded-xl border border-amber-500/30 bg-amber-500/5 shadow-sm">
            <div className="flex items-center gap-2 border-b border-amber-500/20 px-4 py-3">
              <Trophy className="h-4 w-4 text-amber-400" />
              <h3 className="text-sm font-semibold text-amber-300">Best Configuration</h3>
            </div>
            <div className="px-4 py-1">
              <div className="divide-y divide-border/50">
                <BestMetricRow label="RSI Period" value="14" />
                <BestMetricRow label="SMA Period" value="50" />
                <BestMetricRow label="Sharpe Ratio" value="1.82" color="text-emerald-400" />
                <BestMetricRow label="Total Return" value="+24.7%" color="text-emerald-400" />
                <BestMetricRow label="Max Drawdown" value="-8.3%" color="text-red-400" />
                <BestMetricRow label="Win Rate" value="63%" color="text-sky-400" />
              </div>
            </div>

            {/* Sparkline */}
            <div className="px-4 pb-1">
              <p className="mb-1 text-[10px] uppercase tracking-wider text-muted-foreground">
                Equity Curve
              </p>
              <SparklineChart />
            </div>

            <div className="px-4 pb-4 pt-2">
              <Button variant="success" size="sm" className="w-full">
                Apply to Strategy
              </Button>
            </div>
          </div>

          {/* Top 5 combos */}
          <Surface>
            <SurfaceHeader>
              <SurfaceTitle>Top 5 Combos</SurfaceTitle>
            </SurfaceHeader>
            <SurfaceBody className="p-0">
              <div className="divide-y divide-border/50">
                {TOP_COMBOS.map((combo) => (
                  <div
                    key={combo.rank}
                    className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/20"
                  >
                    <RankBadge rank={combo.rank} />
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-mono text-foreground">
                        RSI {combo.rsi} / SMA {combo.sma}
                      </p>
                      <p className="text-[10px] text-muted-foreground">
                        +{combo.ret}%  |  DD {combo.dd}%  |  WR {combo.wr}%
                      </p>
                    </div>
                    <span className="flex-shrink-0 font-mono text-sm font-bold text-emerald-400">
                      {combo.sharpe.toFixed(2)}
                    </span>
                  </div>
                ))}
              </div>
            </SurfaceBody>
          </Surface>

        </div>
      </div>
    </div>
  );
}
