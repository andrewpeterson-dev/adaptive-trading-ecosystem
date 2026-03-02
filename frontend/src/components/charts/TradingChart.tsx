"use client";

import React, { useRef, useEffect, useState, useCallback } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import type { CandleData, TradeMarker, TimeFrame } from "@/types/chart";
import type {
  IChartApi,
  ISeriesApi,
  CandlestickSeriesOptions,
  HistogramSeriesOptions,
  LineSeriesOptions,
  SeriesMarker,
  Time,
} from "lightweight-charts";

const TIMEFRAMES: TimeFrame[] = ["1m", "5m", "15m", "1H", "4H", "1D"];

const CHART_COLORS = {
  background: "#0a0a0f",
  text: "#a1a1aa",
  grid: "#1e293b",
  up: "#10b981",
  down: "#ef4444",
  volume: "#334155",
  sma: "#f59e0b",
  crosshair: "#64748b",
};

function computeSMA(data: CandleData[], period: number): { time: string | number; value: number }[] {
  const result: { time: string | number; value: number }[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) {
      sum += data[i - j].close;
    }
    result.push({ time: data[i].time, value: +(sum / period).toFixed(2) });
  }
  return result;
}

interface TradingChartProps {
  symbol: string;
  height?: number;
  showVolume?: boolean;
  trades?: TradeMarker[];
}

export function TradingChart({
  symbol,
  height = 500,
  showVolume = true,
  trades = [],
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const smaSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);

  const [timeframe, setTimeframe] = useState<TimeFrame>("1D");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAndRender = useCallback(
    async (tf: TimeFrame) => {
      if (!chartRef.current) return;

      setLoading(true);
      setError(null);

      try {
        const res = await fetch(`/api/trading/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${tf}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const { bars } = (await res.json()) as { bars: CandleData[] };

        if (!bars || bars.length === 0) {
          setError("No data available");
          return;
        }

        // Set candle data
        candleSeriesRef.current?.setData(
          bars.map((b) => ({
            time: b.time as Time,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          }))
        );

        // Set volume data
        if (showVolume && volumeSeriesRef.current) {
          volumeSeriesRef.current.setData(
            bars.map((b) => ({
              time: b.time as Time,
              value: b.volume ?? 0,
              color: b.close >= b.open ? CHART_COLORS.up + "40" : CHART_COLORS.down + "40",
            }))
          );
        }

        // Set SMA overlay
        if (smaSeriesRef.current) {
          const smaData = computeSMA(bars, 20);
          smaSeriesRef.current.setData(
            smaData.map((s) => ({ time: s.time as Time, value: s.value }))
          );
        }

        // Trade markers
        if (trades.length > 0 && candleSeriesRef.current) {
          const barTimes = new Set(bars.map((b) => String(b.time)));
          const markers: SeriesMarker<Time>[] = trades
            .filter((t) => barTimes.has(String(t.time)))
            .map((t) => ({
              time: t.time as Time,
              position: t.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const),
              color: t.side === "buy" ? CHART_COLORS.up : CHART_COLORS.down,
              shape: t.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const),
              text: t.side === "buy" ? "B" : "S",
            }))
            .sort((a, b) => {
              const ta = typeof a.time === "string" ? a.time : a.time;
              const tb = typeof b.time === "string" ? b.time : b.time;
              return ta < tb ? -1 : ta > tb ? 1 : 0;
            });

          candleSeriesRef.current.setMarkers(markers);
        }

        chartRef.current.timeScale().fitContent();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load chart data");
      } finally {
        setLoading(false);
      }
    },
    [symbol, showVolume, trades]
  );

  // Initialize chart
  useEffect(() => {
    if (!containerRef.current) return;

    let destroyed = false;
    let chart: IChartApi | null = null;

    async function init() {
      const { createChart } = await import("lightweight-charts");
      if (destroyed || !containerRef.current) return;

      chart = createChart(containerRef.current, {
        width: containerRef.current.clientWidth,
        height,
        layout: {
          background: { color: CHART_COLORS.background },
          textColor: CHART_COLORS.text,
          fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
        },
        grid: {
          vertLines: { color: CHART_COLORS.grid },
          horzLines: { color: CHART_COLORS.grid },
        },
        crosshair: {
          vertLine: { color: CHART_COLORS.crosshair, width: 1, style: 2 },
          horzLine: { color: CHART_COLORS.crosshair, width: 1, style: 2 },
        },
        rightPriceScale: {
          borderColor: CHART_COLORS.grid,
        },
        timeScale: {
          borderColor: CHART_COLORS.grid,
          timeVisible: true,
          secondsVisible: false,
        },
      });

      chartRef.current = chart;

      // Candlestick series
      candleSeriesRef.current = chart.addCandlestickSeries({
        upColor: CHART_COLORS.up,
        downColor: CHART_COLORS.down,
        borderUpColor: CHART_COLORS.up,
        borderDownColor: CHART_COLORS.down,
        wickUpColor: CHART_COLORS.up,
        wickDownColor: CHART_COLORS.down,
      } as CandlestickSeriesOptions);

      // Volume histogram
      if (showVolume) {
        volumeSeriesRef.current = chart.addHistogramSeries({
          priceFormat: { type: "volume" },
          priceScaleId: "volume",
        } as HistogramSeriesOptions);

        chart.priceScale("volume").applyOptions({
          scaleMargins: { top: 0.8, bottom: 0 },
        });
      }

      // SMA line
      smaSeriesRef.current = chart.addLineSeries({
        color: CHART_COLORS.sma,
        lineWidth: 1,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      } as LineSeriesOptions);

      // ResizeObserver
      const observer = new ResizeObserver((entries) => {
        if (chart && entries[0]) {
          const { width } = entries[0].contentRect;
          chart.applyOptions({ width });
        }
      });
      observer.observe(containerRef.current);

      // Fetch initial data
      await fetchAndRender("1D");

      return () => observer.disconnect();
    }

    const cleanupPromise = init();

    return () => {
      destroyed = true;
      cleanupPromise?.then((cleanup) => cleanup?.());
      if (chart) {
        chart.remove();
        chartRef.current = null;
      }
    };
  }, [height, showVolume]); // eslint-disable-line react-hooks/exhaustive-deps

  // Refetch on timeframe or symbol change
  useEffect(() => {
    if (chartRef.current) {
      fetchAndRender(timeframe);
    }
  }, [timeframe, symbol, fetchAndRender]);

  const handleTimeframeChange = (tf: TimeFrame) => {
    setTimeframe(tf);
  };

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className="text-sm font-mono font-bold">{symbol}</span>
          <span className="text-xs text-muted-foreground uppercase tracking-wider">
            Candlestick Chart
          </span>
        </div>
        <div className="flex items-center gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => handleTimeframeChange(tf)}
              className={`px-2 py-1 text-xs font-mono rounded transition-colors ${
                timeframe === tf
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>

      {/* Chart container */}
      <div className="relative" style={{ height }}>
        <div ref={containerRef} className="absolute inset-0" />

        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-card/80 z-10">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 flex flex-col items-center justify-center bg-card/80 z-10 gap-2">
            <AlertTriangle className="h-5 w-5 text-muted-foreground/60" />
            <span className="text-sm text-muted-foreground">{error}</span>
          </div>
        )}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span className="inline-block w-3 h-0.5 rounded" style={{ backgroundColor: CHART_COLORS.sma }} />
          SMA(20)
        </span>
        {showVolume && (
          <span className="flex items-center gap-1.5">
            <span className="inline-block w-3 h-2 rounded-sm" style={{ backgroundColor: CHART_COLORS.volume }} />
            Volume
          </span>
        )}
      </div>
    </div>
  );
}
