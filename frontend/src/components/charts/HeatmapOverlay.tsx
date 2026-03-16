"use client";

import React, { useRef, useEffect, useCallback, useState } from "react";
import type { IChartApi, ISeriesApi } from "lightweight-charts";
import type { AISignal, HeatmapConfig } from "@/types/chart";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HeatmapOverlayProps {
  signals: AISignal[];
  config: HeatmapConfig;
  chartApi: IChartApi | null;
  candleSeries: ISeriesApi<"Candlestick"> | null;
  width: number;
  height: number;
  theme: "dark" | "light";
}

interface PixelSignal {
  x: number;
  y: number;
  strength: number;
  type: "buy" | "sell" | "neutral";
}

interface Cluster {
  x: number;
  y: number;
  avgStrength: number;
  count: number;
  type: "buy" | "sell" | "neutral";
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAX_VISIBLE_POINTS = 500;
const CLUSTER_MERGE_PX = 30;
const BASE_RADIUS = 22;
const MAX_RADIUS = 44;
const MIN_OPACITY = 0.1;
const MAX_OPACITY = 0.6;
const HOVER_HIT_PX = 30;

const COLORS = {
  buy: { dark: "0, 200, 120", light: "16, 185, 129" },
  sell: { dark: "239, 68, 68", light: "220, 38, 38" },
  neutral: { dark: "148, 163, 184", light: "100, 116, 139" },
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function clusterSignals(signals: PixelSignal[], threshold: number): Cluster[] {
  if (signals.length === 0) return [];

  const used = new Set<number>();
  const clusters: Cluster[] = [];

  for (let i = 0; i < signals.length; i++) {
    if (used.has(i)) continue;

    const members: PixelSignal[] = [signals[i]];
    used.add(i);

    for (let j = i + 1; j < signals.length; j++) {
      if (used.has(j)) continue;
      const dx = signals[i].x - signals[j].x;
      const dy = signals[i].y - signals[j].y;
      if (Math.sqrt(dx * dx + dy * dy) < CLUSTER_MERGE_PX) {
        members.push(signals[j]);
        used.add(j);
      }
    }

    if (members.length < threshold) continue;

    // Compute cluster center and average strength
    let sumX = 0, sumY = 0, sumStr = 0;
    const typeCounts: Record<string, number> = { buy: 0, sell: 0, neutral: 0 };
    for (const m of members) {
      sumX += m.x;
      sumY += m.y;
      sumStr += m.strength;
      typeCounts[m.type]++;
    }

    const dominantType =
      typeCounts.buy >= typeCounts.sell && typeCounts.buy >= typeCounts.neutral
        ? "buy"
        : typeCounts.sell >= typeCounts.neutral
          ? "sell"
          : "neutral";

    clusters.push({
      x: sumX / members.length,
      y: sumY / members.length,
      avgStrength: sumStr / members.length,
      count: members.length,
      type: dominantType as "buy" | "sell" | "neutral",
    });
  }

  return clusters;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function HeatmapOverlay({
  signals,
  config,
  chartApi,
  candleSeries,
  width,
  height,
  theme,
}: HeatmapOverlayProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const rafRef = useRef<number>(0);
  const clustersRef = useRef<Cluster[]>([]);
  const [tooltip, setTooltip] = useState<{
    x: number;
    y: number;
    confidence: number;
    count: number;
    type: string;
  } | null>(null);

  // Don't render on mobile
  const isMobile = typeof window !== "undefined" && window.innerWidth < 900;

  // ---------------------------------------------------------------------------
  // Render heatmap
  // ---------------------------------------------------------------------------

  const render = useCallback(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx || !chartApi || !candleSeries || !config.enabled) {
      if (ctx && canvas) {
        ctx.clearRect(0, 0, canvas.width, canvas.height);
      }
      return;
    }

    // Handle high-DPI
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, width, height);

    const timeScale = chartApi.timeScale();
    const visibleRange = timeScale.getVisibleLogicalRange();
    if (!visibleRange) return;

    // Convert signals to pixel coordinates
    const pixelSignals: PixelSignal[] = [];

    for (const signal of signals) {
      // Filter by type visibility
      if (signal.type === "buy" && !config.showBuyZones) continue;
      if (signal.type === "sell" && !config.showSellZones) continue;
      if (signal.type === "neutral") continue;

      const x = timeScale.timeToCoordinate(signal.timestamp as never);
      if (x === null || x < -40 || x > width + 40) continue;

      const y = candleSeries.priceToCoordinate(signal.price);
      if (y === null || y < -40 || y > height + 40) continue;

      pixelSignals.push({
        x,
        y,
        strength: signal.strength,
        type: signal.type,
      });

      if (pixelSignals.length >= MAX_VISIBLE_POINTS) break;
    }

    // Cluster signals
    const clusters = clusterSignals(pixelSignals, config.clusterThreshold);
    clustersRef.current = clusters;

    // Draw heat zones
    for (const cluster of clusters) {
      const colorKey = cluster.type as keyof typeof COLORS;
      const rgb = COLORS[colorKey]?.[theme] ?? COLORS.neutral[theme];
      const radius = Math.min(
        BASE_RADIUS + cluster.count * 3,
        MAX_RADIUS,
      );
      const opacity = Math.min(
        Math.max(cluster.avgStrength * config.intensity, MIN_OPACITY),
        MAX_OPACITY,
      );

      const gradient = ctx.createRadialGradient(
        cluster.x,
        cluster.y,
        0,
        cluster.x,
        cluster.y,
        radius,
      );
      gradient.addColorStop(0, `rgba(${rgb}, ${opacity})`);
      gradient.addColorStop(0.5, `rgba(${rgb}, ${opacity * 0.5})`);
      gradient.addColorStop(1, `rgba(${rgb}, 0)`);

      ctx.beginPath();
      ctx.arc(cluster.x, cluster.y, radius, 0, Math.PI * 2);
      ctx.fillStyle = gradient;
      ctx.fill();
    }
  }, [signals, config, chartApi, candleSeries, width, height, theme]);

  // ---------------------------------------------------------------------------
  // Throttled render via rAF
  // ---------------------------------------------------------------------------

  const scheduleRender = useCallback(() => {
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
    rafRef.current = requestAnimationFrame(render);
  }, [render]);

  // ---------------------------------------------------------------------------
  // Subscribe to chart changes
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!chartApi || !config.enabled) return;

    const timeScale = chartApi.timeScale();
    const handleRangeChange = () => scheduleRender();

    timeScale.subscribeVisibleLogicalRangeChange(handleRangeChange);

    // Initial render
    scheduleRender();

    return () => {
      timeScale.unsubscribeVisibleLogicalRangeChange(handleRangeChange);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [chartApi, config.enabled, scheduleRender]);

  // Re-render when config or signals change
  useEffect(() => {
    scheduleRender();
  }, [scheduleRender, signals, config, width, height, theme]);

  // ---------------------------------------------------------------------------
  // Mouse hover for tooltip
  // ---------------------------------------------------------------------------

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const canvas = canvasRef.current;
      if (!canvas || clustersRef.current.length === 0) {
        setTooltip(null);
        return;
      }

      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;

      let closest: Cluster | null = null;
      let closestDist = HOVER_HIT_PX;

      for (const cluster of clustersRef.current) {
        const dx = mx - cluster.x;
        const dy = my - cluster.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        if (dist < closestDist) {
          closestDist = dist;
          closest = cluster;
        }
      }

      if (closest) {
        setTooltip({
          x: e.clientX - rect.left,
          y: e.clientY - rect.top,
          confidence: Math.round(closest.avgStrength * 100),
          count: closest.count,
          type: closest.type === "buy" ? "Buy bias" : closest.type === "sell" ? "Sell bias" : "Neutral",
        });
      } else {
        setTooltip(null);
      }
    },
    [],
  );

  const handleMouseLeave = useCallback(() => {
    setTooltip(null);
  }, []);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (isMobile || !config.enabled) return null;

  return (
    <>
      <canvas
        ref={canvasRef}
        className="absolute inset-0 pointer-events-auto"
        style={{
          zIndex: 1,
          width,
          height,
        }}
        onMouseMove={handleMouseMove}
        onMouseLeave={handleMouseLeave}
      />
      {tooltip && (
        <div
          ref={tooltipRef}
          className="absolute z-50 pointer-events-none rounded-lg border px-3 py-2 font-mono text-[11px] leading-relaxed shadow-lg"
          style={{
            left: Math.min(tooltip.x + 14, width - 180),
            top: Math.max(tooltip.y - 70, 8),
            backgroundColor: theme === "dark" ? "rgba(8, 17, 31, 0.92)" : "rgba(255, 255, 255, 0.95)",
            borderColor: theme === "dark" ? "rgba(51, 65, 85, 0.6)" : "rgba(203, 213, 225, 0.8)",
            color: theme === "dark" ? "#94a3b8" : "#475569",
          }}
        >
          <div className="font-semibold tracking-wider text-[10px] uppercase mb-1" style={{
            color: theme === "dark" ? "#e2e8f0" : "#1e293b",
          }}>
            AI Signal Cluster
          </div>
          <div>Confidence: <span className="text-foreground font-medium">{tooltip.confidence}%</span></div>
          <div>Detected signals: <span className="text-foreground font-medium">{tooltip.count}</span></div>
          <div>Signal type: <span className={
            tooltip.type === "Buy bias" ? "text-emerald-400 font-medium" : "text-red-400 font-medium"
          }>{tooltip.type}</span></div>
        </div>
      )}
    </>
  );
}
