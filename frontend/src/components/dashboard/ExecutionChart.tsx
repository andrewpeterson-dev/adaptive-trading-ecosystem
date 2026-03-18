"use client";

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { cn } from "@/lib/utils";
import { useThemeMode } from "@/hooks/useThemeMode";
import { useTradeStore } from "@/stores/trade-store";
import type {
  IChartApi,
  ISeriesApi,
  CandlestickSeriesOptions,
  HistogramSeriesOptions,
  SeriesMarker,
  Time,
} from "lightweight-charts";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TradeSignal {
  time: string | number;
  side: "buy" | "sell";
  confidence?: number;
  reason?: string;
}

interface ExecutionChartProps {
  symbol?: string;
  signals?: TradeSignal[];
  height?: number;
}

interface CandleBar {
  time: string | number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface BarsResponse {
  bars: CandleBar[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

type DashboardTimeFrame = "1D" | "1W" | "1M" | "3M" | "1Y";

const TIMEFRAMES: DashboardTimeFrame[] = ["1D", "1W", "1M", "3M", "1Y"];

const CHART_COLORS = {
  up: "#10b981",
  down: "#ef4444",
  volume: "#334155",
};

const LIGHT_THEME = {
  background: "#ffffff",
  text: "#475569",
  grid: "#e2e8f0",
  border: "#cbd5e1",
  crosshair: "#94a3b8",
};

const DARK_THEME = {
  background: "#08111f",
  text: "#94a3b8",
  grid: "#1e293b",
  border: "#334155",
  crosshair: "#64748b",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function toEpochMs(value: string | number): number | null {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value > 1_000_000_000_000 ? value : value * 1000;
  }
  if (typeof value === "string") {
    const numeric = Number(value);
    if (Number.isFinite(numeric) && value.trim() !== "") {
      return numeric > 1_000_000_000_000 ? numeric : numeric * 1000;
    }
    const parsed = Date.parse(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

function findNearestBarTime(
  targetTime: string | number,
  bars: CandleBar[],
): string | number | null {
  const targetMs = toEpochMs(targetTime);
  if (targetMs == null || bars.length === 0) return null;

  let nearestTime: string | number | null = null;
  let bestDiff = Number.POSITIVE_INFINITY;

  for (const bar of bars) {
    const barMs = toEpochMs(bar.time);
    if (barMs == null) continue;
    const diff = Math.abs(barMs - targetMs);
    if (diff < bestDiff) {
      bestDiff = diff;
      nearestTime = bar.time;
    }
  }

  return nearestTime;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ExecutionChart({
  symbol: symbolProp,
  signals = [],
  height = 400,
}: ExecutionChartProps) {
  const storeSymbol = useTradeStore((state) => state.symbol);
  const symbol = symbolProp || storeSymbol || "";
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const observerRef = useRef<ResizeObserver | null>(null);
  const initPromiseRef = useRef<Promise<void> | null>(null);
  const barsRef = useRef<CandleBar[]>([]);

  const { theme } = useThemeMode();
  const chartTheme = useMemo(
    () => (theme === "dark" ? DARK_THEME : LIGHT_THEME),
    [theme],
  );

  const [timeframe, setTimeframe] = useState<DashboardTimeFrame>("1M");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // ---------------------------------------------------------------------------
  // Signal markers
  // ---------------------------------------------------------------------------

  const applySignalMarkers = useCallback(
    (bars: CandleBar[], sigs: TradeSignal[]) => {
      if (!candleSeriesRef.current) return;

      if (sigs.length === 0) {
        candleSeriesRef.current.setMarkers([]);
        return;
      }

      const markers = sigs
        .reduce<SeriesMarker<Time>[]>((acc, sig) => {
          const nearestBarTime = findNearestBarTime(sig.time, bars);
          if (nearestBarTime == null) return acc;

          const isBuy = sig.side === "buy";
          acc.push({
            time: nearestBarTime as Time,
            position: isBuy ? "belowBar" : "aboveBar",
            color: isBuy ? CHART_COLORS.up : CHART_COLORS.down,
            shape: isBuy ? "arrowUp" : "arrowDown",
            text: isBuy ? "BUY" : "SELL",
            size: 1,
          });
          return acc;
        }, [])
        .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

      candleSeriesRef.current.setMarkers(markers);
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Fetch data
  // ---------------------------------------------------------------------------

  const fetchAndRender = useCallback(
    async (tf: DashboardTimeFrame) => {
      if (!chartRef.current || !symbol) return;

      setLoading(true);
      setError(null);

      try {
        const safeLimit = Math.max(300, 50);
        const res = await fetch(
          `/api/trading/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${tf}&limit=${safeLimit}`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = (await res.json()) as BarsResponse;
        const { bars } = payload;

        if (!bars || bars.length === 0) {
          setError(`No data available for ${symbol}`);
          return;
        }

        barsRef.current = bars;

        candleSeriesRef.current?.setData(
          bars.map((b) => ({
            time: b.time as Time,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          })),
        );

        volumeSeriesRef.current?.setData(
          bars.map((b) => ({
            time: b.time as Time,
            value: b.volume ?? 0,
            color:
              b.close >= b.open
                ? CHART_COLORS.up + "40"
                : CHART_COLORS.down + "40",
          })),
        );

        applySignalMarkers(bars, signals);
        chartRef.current.timeScale().fitContent();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load chart data");
      } finally {
        setLoading(false);
      }
    },
    [symbol, signals, applySignalMarkers],
  );

  // ---------------------------------------------------------------------------
  // Re-apply markers when signals change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (barsRef.current.length > 0) {
      applySignalMarkers(barsRef.current, signals);
    }
  }, [signals, applySignalMarkers]);

  // ---------------------------------------------------------------------------
  // Chart init
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;
    let chart: IChartApi | null = null;

    const init = async () => {
      const { createChart } = await import("lightweight-charts");
      if (destroyed || !containerRef.current) return;

      chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height,
        layout: {
          background: { color: chartTheme.background },
          textColor: chartTheme.text,
          fontFamily:
            "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
        },
        grid: {
          vertLines: { color: chartTheme.grid },
          horzLines: { color: chartTheme.grid },
        },
        crosshair: {
          vertLine: { color: chartTheme.crosshair, width: 1, style: 2 },
          horzLine: { color: chartTheme.crosshair, width: 1, style: 2 },
        },
        rightPriceScale: {
          borderColor: chartTheme.border,
        },
        timeScale: {
          borderColor: chartTheme.border,
          timeVisible: true,
          secondsVisible: false,
        },
      });

      chartRef.current = chart;

      candleSeriesRef.current = chart.addCandlestickSeries({
        upColor: CHART_COLORS.up,
        downColor: CHART_COLORS.down,
        borderUpColor: CHART_COLORS.up,
        borderDownColor: CHART_COLORS.down,
        wickUpColor: CHART_COLORS.up,
        wickDownColor: CHART_COLORS.down,
      } as CandlestickSeriesOptions);

      volumeSeriesRef.current = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
      } as HistogramSeriesOptions);
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      const observer = new ResizeObserver((entries) => {
        if (chart && entries[0]) {
          const { width } = entries[0].contentRect;
          chart.applyOptions({ width });
        }
      });
      observer.observe(containerRef.current);
      observerRef.current = observer;

      await fetchAndRender(timeframe);
    };

    initPromiseRef.current = init();

    return () => {
      destroyed = true;
      observerRef.current?.disconnect();
      observerRef.current = null;
      if (chart) {
        chart.remove();
        chartRef.current = null;
        candleSeriesRef.current = null;
        volumeSeriesRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ---------------------------------------------------------------------------
  // Theme updates
  // ---------------------------------------------------------------------------

  useEffect(() => {
    chartRef.current?.applyOptions({
      layout: {
        background: { color: chartTheme.background },
        textColor: chartTheme.text,
        fontFamily:
          "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
      },
      grid: {
        vertLines: { color: chartTheme.grid },
        horzLines: { color: chartTheme.grid },
      },
      crosshair: {
        vertLine: { color: chartTheme.crosshair, width: 1, style: 2 },
        horzLine: { color: chartTheme.crosshair, width: 1, style: 2 },
      },
      rightPriceScale: { borderColor: chartTheme.border },
      timeScale: {
        borderColor: chartTheme.border,
        timeVisible: true,
        secondsVisible: false,
      },
    });
  }, [chartTheme]);

  // ---------------------------------------------------------------------------
  // Height updates
  // ---------------------------------------------------------------------------

  useEffect(() => {
    chartRef.current?.applyOptions({ height });
  }, [height]);

  // ---------------------------------------------------------------------------
  // Re-fetch on symbol or timeframe change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (initPromiseRef.current) {
      initPromiseRef.current.then(() => {
        if (chartRef.current) {
          fetchAndRender(timeframe);
        }
      });
    }
  }, [timeframe, symbol, fetchAndRender]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  if (!symbol) {
    return (
      <div
        className="flex items-center justify-center rounded-md bg-muted/20 text-xs text-muted-foreground"
        style={{ height }}
      >
        Select a symbol to view chart
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {/* Timeframe selector */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-mono font-semibold text-muted-foreground">
          {symbol}
        </span>
        <div className="flex items-center gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              type="button"
              onClick={() => setTimeframe(tf)}
              className={cn(
                "rounded-full px-2.5 py-1 text-[10px] font-mono font-semibold transition-colors",
                timeframe === tf
                  ? "bg-foreground text-background"
                  : "bg-black/[0.03] text-muted-foreground hover:text-foreground dark:bg-white/[0.03]",
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div className="relative overflow-hidden rounded-md" style={{ height }}>
        <div ref={containerRef} className="absolute inset-0" />

        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-background/80 backdrop-blur-sm">
            <AlertTriangle className="h-5 w-5 text-muted-foreground/60" />
            <span className="text-sm font-semibold text-foreground">
              Chart data unavailable
            </span>
            <span className="max-w-sm text-center text-xs text-muted-foreground">
              {error?.includes("Internal Server") ? "The server is temporarily unavailable. Try again shortly." : error}
            </span>
            <button
              type="button"
              onClick={() => void fetchAndRender(timeframe)}
              className="mt-1 rounded-md bg-foreground/10 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-foreground/20"
            >
              Retry
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
