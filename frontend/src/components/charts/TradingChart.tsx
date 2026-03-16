"use client";

import React, { useRef, useEffect, useState, useCallback, useMemo } from "react";
import { Loader2, AlertTriangle } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import { useThemeMode } from "@/hooks/useThemeMode";
import { Button } from "@/components/ui/button";
import { HeatmapOverlay } from "@/components/charts/HeatmapOverlay";
import { ChartOverlaySettings } from "@/components/charts/ChartOverlaySettings";
import type { CandleData, TradeMarker, TimeFrame, ChartIndicator, PriceLevelLine, AISignal, HeatmapConfig } from "@/types/chart";
import type {
  IChartApi,
  ISeriesApi,
  CandlestickSeriesOptions,
  HistogramSeriesOptions,
  LineSeriesOptions,
  SeriesMarker,
  Time,
  IPriceLine,
} from "lightweight-charts";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const TIMEFRAMES: TimeFrame[] = ["1m", "5m", "15m", "1H", "4H", "1D", "1W"];

const CHART_COLORS = {
  up: "#10b981",
  down: "#ef4444",
  volume: "#334155",
  sma20: "#f59e0b",
  sma50: "#3b82f6",
  ema9: "#a855f7",
  vwap: "#06b6d4",
  rsi: "#e879f9",
  macdLine: "#38bdf8",
  macdSignal: "#fb923c",
  crosshair: "#64748b",
};

const LIGHT_CHART_THEME = {
  background: "#ffffff",
  text: "#475569",
  grid: "#e2e8f0",
  border: "#cbd5e1",
  crosshair: "#94a3b8",
};

const DARK_CHART_THEME = {
  background: "#08111f",
  text: "#94a3b8",
  grid: "#1e293b",
  border: "#334155",
  crosshair: "#64748b",
};

const INDICATOR_META: Record<ChartIndicator, { label: string; color: string }> = {
  sma20: { label: "SMA 20", color: CHART_COLORS.sma20 },
  sma50: { label: "SMA 50", color: CHART_COLORS.sma50 },
  ema9: { label: "EMA 9", color: CHART_COLORS.ema9 },
  vwap: { label: "VWAP", color: CHART_COLORS.vwap },
  volume: { label: "Volume", color: CHART_COLORS.volume },
  rsi: { label: "RSI", color: CHART_COLORS.rsi },
  macd: { label: "MACD", color: CHART_COLORS.macdLine },
};

const ALL_INDICATORS: ChartIndicator[] = ["sma20", "sma50", "ema9", "vwap", "volume", "rsi", "macd"];

// ---------------------------------------------------------------------------
// Computation helpers
// ---------------------------------------------------------------------------

type PointData = { time: string | number; value: number };
type HistogramPointData = PointData & { color?: string };

interface BarsResponse {
  bars: CandleData[];
  indicators?: {
    rsi?: Array<{ time: string | number; value: number }>;
    macd?: {
      macd?: Array<{ time: string | number; value: number }>;
      macdLine?: Array<{ time: string | number; value: number }>;
      macd_line?: Array<{ time: string | number; value: number }>;
      signal?: Array<{ time: string | number; value: number }>;
      signalLine?: Array<{ time: string | number; value: number }>;
      signal_line?: Array<{ time: string | number; value: number }>;
      histogram?: Array<{
        time: string | number;
        value: number;
        color?: string;
      }>;
    };
  };
}

function normalizeLineSeries(points: Array<{ time: string | number; value: number }> | undefined): PointData[] {
  if (!points) return [];
  return points
    .filter((point) => Number.isFinite(point?.value))
    .map((point) => ({ time: point.time, value: Number(point.value) }));
}

function normalizeHistogramSeries(
  points:
    | Array<{ time: string | number; value: number; color?: string }>
    | undefined
): HistogramPointData[] {
  if (!points) return [];
  return points
    .filter((point) => Number.isFinite(point?.value))
    .map((point) => ({
      time: point.time,
      value: Number(point.value),
      color: point.color,
    }));
}

function resolveVisibleTrades(
  trades: TradeMarker[],
  showAllExecutions: boolean,
  highlightedTradeId: string | null,
): TradeMarker[] {
  if (!showAllExecutions && highlightedTradeId) {
    return trades.filter((trade) => trade.tradeId === highlightedTradeId);
  }
  return showAllExecutions ? trades : [];
}

function normalizeTradeTime(value: unknown): string | null {
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (
    typeof value === "object" &&
    value !== null &&
    "year" in value &&
    "month" in value &&
    "day" in value
  ) {
    const businessDay = value as { year: number; month: number; day: number };
    return `${businessDay.year}-${String(businessDay.month).padStart(2, "0")}-${String(
      businessDay.day,
    ).padStart(2, "0")}`;
  }
  return null;
}

function toEpochMs(value: unknown): number | null {
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
  if (
    typeof value === "object" &&
    value !== null &&
    "year" in value &&
    "month" in value &&
    "day" in value
  ) {
    const businessDay = value as { year: number; month: number; day: number };
    return Date.UTC(businessDay.year, businessDay.month - 1, businessDay.day);
  }
  return null;
}

function findNearestBarTime(targetTime: unknown, bars: CandleData[]): string | number | null {
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

function findTradeMarkerForTime(
  trades: TradeMarker[],
  time: unknown,
  highlightedTradeId: string | null,
  bars: CandleData[],
): TradeMarker | null {
  const normalizedTime = normalizeTradeTime(time);
  if (!normalizedTime) return null;

  const matches = trades.filter((trade) => {
    const nearestBarTime = findNearestBarTime(trade.time, bars);
    return normalizeTradeTime(nearestBarTime) === normalizedTime;
  });
  if (matches.length === 0) return null;

  return (
    matches.find((trade) => trade.tradeId != null && trade.tradeId === highlightedTradeId) ??
    matches[0]
  );
}

function computeSMA(data: CandleData[], period: number): PointData[] {
  const result: PointData[] = [];
  for (let i = period - 1; i < data.length; i++) {
    let sum = 0;
    for (let j = 0; j < period; j++) sum += data[i - j].close;
    result.push({ time: data[i].time, value: +(sum / period).toFixed(4) });
  }
  return result;
}

function computeEMA(data: CandleData[], period: number): PointData[] {
  const result: PointData[] = [];
  const k = 2 / (period + 1);
  let ema = data[0]?.close ?? 0;
  for (let i = 0; i < data.length; i++) {
    ema = (data[i].close - ema) * k + ema;
    if (i >= period - 1) result.push({ time: data[i].time, value: +ema.toFixed(4) });
  }
  return result;
}

function computeEMAFromValues(values: number[], period: number): number[] {
  const result: number[] = [];
  const k = 2 / (period + 1);
  let ema = values[0] ?? 0;
  for (let i = 0; i < values.length; i++) {
    ema = (values[i] - ema) * k + ema;
    result.push(ema);
  }
  return result;
}

function computeVWAP(data: CandleData[]): PointData[] {
  const result: PointData[] = [];
  let cumTPV = 0;
  let cumVol = 0;
  for (const bar of data) {
    const vol = bar.volume ?? 0;
    if (vol === 0) continue;
    const tp = (bar.high + bar.low + bar.close) / 3;
    cumTPV += tp * vol;
    cumVol += vol;
    result.push({ time: bar.time, value: +(cumTPV / cumVol).toFixed(4) });
  }
  return result;
}

function computeRSI(data: CandleData[], period: number = 14): PointData[] {
  if (data.length < period + 1) return [];
  const result: PointData[] = [];
  const changes: number[] = [];
  for (let i = 1; i < data.length; i++) {
    changes.push(data[i].close - data[i - 1].close);
  }

  // Initial averages (simple)
  let avgGain = 0;
  let avgLoss = 0;
  for (let i = 0; i < period; i++) {
    if (changes[i] > 0) avgGain += changes[i];
    else avgLoss += Math.abs(changes[i]);
  }
  avgGain /= period;
  avgLoss /= period;

  const rsi0 = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
  result.push({ time: data[period].time, value: +rsi0.toFixed(2) });

  // Smoothed (Wilder's)
  for (let i = period; i < changes.length; i++) {
    const change = changes[i];
    const gain = change > 0 ? change : 0;
    const loss = change < 0 ? Math.abs(change) : 0;
    avgGain = (avgGain * (period - 1) + gain) / period;
    avgLoss = (avgLoss * (period - 1) + loss) / period;
    const rsi = avgLoss === 0 ? 100 : 100 - 100 / (1 + avgGain / avgLoss);
    result.push({ time: data[i + 1].time, value: +rsi.toFixed(2) });
  }
  return result;
}

interface MACDResult {
  macdLine: PointData[];
  signalLine: PointData[];
  histogram: { time: string | number; value: number; color: string }[];
}

function normalizeMACDSeries(
  macd:
    | {
        macd?: Array<{ time: string | number; value: number }>;
        macdLine?: Array<{ time: string | number; value: number }>;
        macd_line?: Array<{ time: string | number; value: number }>;
        signal?: Array<{ time: string | number; value: number }>;
        signalLine?: Array<{ time: string | number; value: number }>;
        signal_line?: Array<{ time: string | number; value: number }>;
        histogram?: Array<{
          time: string | number;
          value: number;
          color?: string;
        }>;
      }
    | undefined
): MACDResult | null {
  if (!macd) return null;

  const macdLine = normalizeLineSeries(macd.macdLine ?? macd.macd_line ?? macd.macd);
  const signalLine = normalizeLineSeries(macd.signalLine ?? macd.signal_line ?? macd.signal);
  const histogram = normalizeHistogramSeries(macd.histogram).map((point) => ({
    time: point.time,
    value: point.value,
    color:
      point.color ??
      (point.value >= 0 ? CHART_COLORS.up + "b0" : CHART_COLORS.down + "b0"),
  }));

  if (macdLine.length === 0 || signalLine.length === 0 || histogram.length === 0) {
    return null;
  }

  return { macdLine, signalLine, histogram };
}

function computeMACD(data: CandleData[], fast = 12, slow = 26, signal = 9): MACDResult {
  const closes = data.map((d) => d.close);
  const emaFast = computeEMAFromValues(closes, fast);
  const emaSlow = computeEMAFromValues(closes, slow);

  // MACD line starts at index slow-1 (when slow EMA is meaningful)
  const startIdx = slow - 1;
  const macdValues: number[] = [];
  const macdLine: PointData[] = [];

  for (let i = startIdx; i < data.length; i++) {
    const val = +(emaFast[i] - emaSlow[i]).toFixed(4);
    macdValues.push(val);
    macdLine.push({ time: data[i].time, value: val });
  }

  const signalValues = computeEMAFromValues(macdValues, signal);
  const signalLine: PointData[] = [];
  const histogram: { time: string | number; value: number; color: string }[] = [];

  // Signal starts at index signal-1 within macdValues
  const sigStart = signal - 1;
  for (let i = sigStart; i < macdValues.length; i++) {
    const dataIdx = startIdx + i;
    const sig = +signalValues[i].toFixed(4);
    const hist = +(macdValues[i] - sig).toFixed(4);
    signalLine.push({ time: data[dataIdx].time, value: sig });
    histogram.push({
      time: data[dataIdx].time,
      value: hist,
      color: hist >= 0 ? CHART_COLORS.up + "b0" : CHART_COLORS.down + "b0",
    });
  }

  return { macdLine: macdLine.slice(sigStart), signalLine, histogram };
}

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TradingChartProps {
  symbol: string;
  height?: number;
  showVolume?: boolean;
  trades?: TradeMarker[];
  highlightedTradeId?: string | null;
  priceLevels?: PriceLevelLine[];
  onTradeHover?: (tradeId: string | null) => void;
  onTradeSelect?: (tradeId: string | null) => void;
}

function getResponsiveHeight(baseHeight: number, viewportWidth: number): number {
  if (viewportWidth < 640) return Math.min(baseHeight, 340);
  if (viewportWidth < 1024) return Math.min(baseHeight, 420);
  return baseHeight;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function TradingChart({
  symbol,
  height = 500,
  showVolume = true,
  trades = [],
  highlightedTradeId = null,
  priceLevels = [],
  onTradeHover,
  onTradeSelect,
}: TradingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const { theme } = useThemeMode();
  const chartTheme = useMemo(
    () => (theme === "dark" ? DARK_CHART_THEME : LIGHT_CHART_THEME),
    [theme],
  );

  // Series refs — created once at init, visibility toggled
  const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
  const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);
  const sma20SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const sma50SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const ema9SeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const vwapSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const rsiSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdLineSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdSignalSeriesRef = useRef<ISeriesApi<"Line"> | null>(null);
  const macdHistSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

  const priceLinesRef = useRef<IPriceLine[]>([]);
  const rsiLinesRef = useRef<IPriceLine[]>([]);
  const barsRef = useRef<CandleData[]>([]);
  const observerRef = useRef<ResizeObserver | null>(null);
  const initPromiseRef = useRef<Promise<void> | null>(null);
  const tradesRef = useRef<TradeMarker[]>(trades);
  const highlightedTradeIdRef = useRef<string | null>(highlightedTradeId);
  const onTradeHoverRef = useRef<typeof onTradeHover>(onTradeHover);
  const onTradeSelectRef = useRef<typeof onTradeSelect>(onTradeSelect);
  const hoveredMarkerIdRef = useRef<string | null>(null);

  const [timeframe, setTimeframe] = useState<TimeFrame>("1D");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [chartHeight, setChartHeight] = useState(height);
  const [indicators, setIndicators] = useState<Record<ChartIndicator, boolean>>({
    sma20: true,
    sma50: false,
    ema9: false,
    vwap: false,
    volume: showVolume,
    rsi: false,
    macd: false,
  });

  const { quote, positions, showAllExecutions, setShowAllExecutions } = useTradeStore();
  const showAllExecutionsRef = useRef(showAllExecutions);

  // --- AI Heatmap state ---
  const [aiSignals, setAiSignals] = useState<AISignal[]>([]);
  const [aiSignalsEnabled, setAiSignalsEnabled] = useState(true);
  const [tradeMarkersEnabled, setTradeMarkersEnabled] = useState(true);
  const [indicatorsVisible, setIndicatorsVisible] = useState(true);
  const [heatmapConfig, setHeatmapConfig] = useState<HeatmapConfig>({
    enabled: false,
    intensity: 0.65,
    clusterThreshold: 1,
    showBuyZones: true,
    showSellZones: true,
  });
  const [chartDimensions, setChartDimensions] = useState({ width: 0, height: 0 });

  const hasSubIndicator = indicators.rsi || indicators.macd;
  const hasBothSub = indicators.rsi && indicators.macd;

  useEffect(() => {
    tradesRef.current = trades;
    highlightedTradeIdRef.current = highlightedTradeId;
    onTradeHoverRef.current = onTradeHover;
    onTradeSelectRef.current = onTradeSelect;
  }, [trades, highlightedTradeId, onTradeHover, onTradeSelect]);

  useEffect(() => {
    showAllExecutionsRef.current = showAllExecutions;
  }, [showAllExecutions]);

  // ---------------------------------------------------------------------------
  // Toggle handler
  // ---------------------------------------------------------------------------

  const toggleIndicator = useCallback((ind: ChartIndicator) => {
    setIndicators((prev) => ({ ...prev, [ind]: !prev[ind] }));
  }, []);

  useEffect(() => {
    const updateHeight = () => {
      setChartHeight(getResponsiveHeight(height, window.innerWidth));
    };

    updateHeight();
    window.addEventListener("resize", updateHeight);
    return () => window.removeEventListener("resize", updateHeight);
  }, [height]);

  // ---------------------------------------------------------------------------
  // Update scale margins when sub-indicators change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart) return;

    // Volume margins
    const volumeMargins = hasSubIndicator
      ? { top: 0.65, bottom: 0.08 }
      : { top: 0.8, bottom: 0 };
    chart.priceScale("volume").applyOptions({ scaleMargins: volumeMargins });

    // RSI margins
    if (rsiSeriesRef.current) {
      const rsiMargins = hasBothSub
        ? { top: 0.72, bottom: 0.15 }
        : { top: 0.78, bottom: 0.02 };
      chart.priceScale("rsi").applyOptions({ scaleMargins: rsiMargins });
    }

    // MACD margins
    if (macdLineSeriesRef.current) {
      const macdMargins = hasBothSub
        ? { top: 0.86, bottom: 0.02 }
        : { top: 0.78, bottom: 0.02 };
      chart.priceScale("macd").applyOptions({ scaleMargins: macdMargins });
    }
  }, [hasSubIndicator, hasBothSub, indicators.rsi, indicators.macd]);

  // ---------------------------------------------------------------------------
  // Apply indicator visibility
  // ---------------------------------------------------------------------------

  useEffect(() => {
    sma20SeriesRef.current?.applyOptions({ visible: indicators.sma20 });
    sma50SeriesRef.current?.applyOptions({ visible: indicators.sma50 });
    ema9SeriesRef.current?.applyOptions({ visible: indicators.ema9 });
    vwapSeriesRef.current?.applyOptions({ visible: indicators.vwap });
    volumeSeriesRef.current?.applyOptions({ visible: indicators.volume });
    rsiSeriesRef.current?.applyOptions({ visible: indicators.rsi });
    macdLineSeriesRef.current?.applyOptions({ visible: indicators.macd });
    macdSignalSeriesRef.current?.applyOptions({ visible: indicators.macd });
    macdHistSeriesRef.current?.applyOptions({ visible: indicators.macd });

    // RSI reference lines (30/70) are attached to the RSI series.
    // When the RSI series is hidden, its price lines are also hidden
    // automatically by lightweight-charts. No extra action needed.
  }, [indicators]);

  // ---------------------------------------------------------------------------
  // Position price lines
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!candleSeriesRef.current) return;

    // Remove old price lines
    for (const line of priceLinesRef.current) {
      try {
        candleSeriesRef.current.removePriceLine(line);
      } catch {
        /* series may have been removed */
      }
    }
    priceLinesRef.current = [];

    const matchingPositions = positions.filter(
      (p) => p.symbol.toUpperCase() === symbol.toUpperCase(),
    );

    for (const pos of matchingPositions) {
      if (pos.avg_entry_price && candleSeriesRef.current) {
        const entryLine = candleSeriesRef.current.createPriceLine({
          price: pos.avg_entry_price,
          color: CHART_COLORS.up,
          lineWidth: 1,
          lineStyle: 2, // dashed
          axisLabelVisible: true,
          title: `Entry ${(pos.side ?? "LONG").toUpperCase()}`,
        });
        priceLinesRef.current.push(entryLine);
      }

      if (pos.stop_loss != null && candleSeriesRef.current) {
        const slLine = candleSeriesRef.current.createPriceLine({
          price: pos.stop_loss,
          color: CHART_COLORS.down,
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Stop Loss",
        });
        priceLinesRef.current.push(slLine);
      }

      if (pos.take_profit != null && candleSeriesRef.current) {
        const tpLine = candleSeriesRef.current.createPriceLine({
          price: pos.take_profit,
          color: "#34d399", // emerald-400
          lineWidth: 1,
          lineStyle: 2,
          axisLabelVisible: true,
          title: "Take Profit",
        });
        priceLinesRef.current.push(tpLine);
      }
    }

    for (const level of priceLevels) {
      if (!candleSeriesRef.current) continue;
      const line = candleSeriesRef.current.createPriceLine({
        price: level.price,
        color: level.color,
        lineWidth: 1,
        lineStyle: level.lineStyle ?? 2,
        axisLabelVisible: true,
        title: level.label,
      });
      priceLinesRef.current.push(line);
    }
  }, [positions, symbol, priceLevels]);

  // ---------------------------------------------------------------------------
  // Fetch and render data
  // ---------------------------------------------------------------------------

  const fetchAndRender = useCallback(
    async (tf: TimeFrame) => {
      if (!chartRef.current) return;

      setLoading(true);
      setError(null);

      try {
        const res = await fetch(
          `/api/trading/bars?symbol=${encodeURIComponent(symbol)}&timeframe=${tf}&limit=300`,
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const payload = (await res.json()) as BarsResponse;
        const { bars } = payload;

        if (!bars || bars.length === 0) {
          setError(`No data available for ${symbol}`);
          return;
        }

        barsRef.current = bars;

        // --- Candlestick ---
        candleSeriesRef.current?.setData(
          bars.map((b) => ({
            time: b.time as Time,
            open: b.open,
            high: b.high,
            low: b.low,
            close: b.close,
          })),
        );

        // --- Volume ---
        volumeSeriesRef.current?.setData(
          bars.map((b) => ({
            time: b.time as Time,
            value: b.volume ?? 0,
            color: b.close >= b.open ? CHART_COLORS.up + "40" : CHART_COLORS.down + "40",
          })),
        );

        // --- SMA 20 ---
        sma20SeriesRef.current?.setData(
          computeSMA(bars, 20).map((s) => ({ time: s.time as Time, value: s.value })),
        );

        // --- SMA 50 ---
        sma50SeriesRef.current?.setData(
          computeSMA(bars, 50).map((s) => ({ time: s.time as Time, value: s.value })),
        );

        // --- EMA 9 ---
        ema9SeriesRef.current?.setData(
          computeEMA(bars, 9).map((s) => ({ time: s.time as Time, value: s.value })),
        );

        // --- VWAP ---
        vwapSeriesRef.current?.setData(
          computeVWAP(bars).map((s) => ({ time: s.time as Time, value: s.value })),
        );

        // --- RSI ---
        if (rsiSeriesRef.current) {
          const rsiData =
            normalizeLineSeries(payload.indicators?.rsi).length > 0
              ? normalizeLineSeries(payload.indicators?.rsi)
              : computeRSI(bars, 14);
          rsiSeriesRef.current.setData(
            rsiData.map((s) => ({ time: s.time as Time, value: s.value })),
          );
        }

        // --- MACD ---
        if (macdLineSeriesRef.current && macdSignalSeriesRef.current && macdHistSeriesRef.current) {
          const macd = normalizeMACDSeries(payload.indicators?.macd) ?? computeMACD(bars, 12, 26, 9);
          macdLineSeriesRef.current.setData(
            macd.macdLine.map((s) => ({ time: s.time as Time, value: s.value })),
          );
          macdSignalSeriesRef.current.setData(
            macd.signalLine.map((s) => ({ time: s.time as Time, value: s.value })),
          );
          macdHistSeriesRef.current.setData(
            macd.histogram.map((s) => ({
              time: s.time as Time,
              value: s.value,
              color: s.color,
            })),
          );
        }

        // --- Trade markers ---
        applyTradeMarkers(bars);

        chartRef.current.timeScale().fitContent();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load chart data");
      } finally {
        setLoading(false);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [symbol],
  );

  // ---------------------------------------------------------------------------
  // Trade markers helper
  // ---------------------------------------------------------------------------

  const applyTradeMarkers = useCallback(
    (bars: CandleData[]) => {
      if (!candleSeriesRef.current) return;

      const visibleTrades = resolveVisibleTrades(trades, showAllExecutions, highlightedTradeId);

      if (visibleTrades.length === 0) {
        candleSeriesRef.current.setMarkers([]);
        return;
      }

      const markers = visibleTrades.reduce<SeriesMarker<Time>[]>((acc, t) => {
          const nearestBarTime = findNearestBarTime(t.time, bars);
          if (nearestBarTime == null) {
            return acc;
          }
          const isHighlighted = highlightedTradeId != null && t.tradeId === highlightedTradeId;
          acc.push({
            time: nearestBarTime as Time,
            position:
              t.position ?? (t.side === "buy" ? ("belowBar" as const) : ("aboveBar" as const)),
            color: t.color ?? (t.side === "buy" ? CHART_COLORS.up : CHART_COLORS.down),
            shape:
              t.shape ?? (t.side === "buy" ? ("arrowUp" as const) : ("arrowDown" as const)),
            text: t.text ?? t.label ?? (t.side === "buy" ? "B" : "S"),
            size: isHighlighted ? 2 : 1,
          });
          return acc;
        }, [])
        .sort((a, b) => (a.time < b.time ? -1 : a.time > b.time ? 1 : 0));

      candleSeriesRef.current.setMarkers(markers);
    },
    [trades, showAllExecutions, highlightedTradeId],
  );

  // Re-apply markers when trades/showAllExecutions/highlightedTradeId change
  useEffect(() => {
    if (barsRef.current.length > 0) {
      applyTradeMarkers(barsRef.current);
    }
  }, [applyTradeMarkers]);

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
        height: chartHeight,
        layout: {
          background: { color: chartTheme.background },
          textColor: chartTheme.text,
          fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
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

      // -- Candlestick --
      candleSeriesRef.current = chart.addCandlestickSeries({
        upColor: CHART_COLORS.up,
        downColor: CHART_COLORS.down,
        borderUpColor: CHART_COLORS.up,
        borderDownColor: CHART_COLORS.down,
        wickUpColor: CHART_COLORS.up,
        wickDownColor: CHART_COLORS.down,
      } as CandlestickSeriesOptions);

      // -- Volume --
      volumeSeriesRef.current = chart.addHistogramSeries({
        priceFormat: { type: "volume" },
        priceScaleId: "volume",
        visible: indicators.volume,
      } as HistogramSeriesOptions);
      chart.priceScale("volume").applyOptions({
        scaleMargins: { top: 0.8, bottom: 0 },
      });

      // -- Overlay lines --
      const overlayLineDefaults = {
        lineWidth: 1 as const,
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
      };

      sma20SeriesRef.current = chart.addLineSeries({
        ...overlayLineDefaults,
        color: CHART_COLORS.sma20,
        visible: indicators.sma20,
      } as LineSeriesOptions);

      sma50SeriesRef.current = chart.addLineSeries({
        ...overlayLineDefaults,
        color: CHART_COLORS.sma50,
        visible: indicators.sma50,
      } as LineSeriesOptions);

      ema9SeriesRef.current = chart.addLineSeries({
        ...overlayLineDefaults,
        color: CHART_COLORS.ema9,
        visible: indicators.ema9,
      } as LineSeriesOptions);

      vwapSeriesRef.current = chart.addLineSeries({
        ...overlayLineDefaults,
        color: CHART_COLORS.vwap,
        visible: indicators.vwap,
        lineWidth: 2 as const,
      } as LineSeriesOptions);

      // -- RSI (separate pane via priceScaleId) --
      rsiSeriesRef.current = chart.addLineSeries({
        color: CHART_COLORS.rsi,
        lineWidth: 1,
        priceScaleId: "rsi",
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: indicators.rsi,
      } as LineSeriesOptions);

      chart.priceScale("rsi").applyOptions({
        scaleMargins: { top: 0.78, bottom: 0.02 },
        autoScale: true,
      });

      // RSI reference lines at 30 and 70
      if (rsiSeriesRef.current) {
        // We need data before creating price lines; we'll add them after first data set.
        // Instead, create them now — lightweight-charts handles them even without data.
        const rsi30 = rsiSeriesRef.current.createPriceLine({
          price: 30,
          color: CHART_COLORS.rsi + "50",
          lineWidth: 1,
          lineStyle: 1, // dotted
          axisLabelVisible: false,
          title: "",
        });
        const rsi70 = rsiSeriesRef.current.createPriceLine({
          price: 70,
          color: CHART_COLORS.rsi + "50",
          lineWidth: 1,
          lineStyle: 1,
          axisLabelVisible: false,
          title: "",
        });
        rsiLinesRef.current = [rsi30, rsi70];
      }

      // -- MACD (separate pane via priceScaleId) --
      macdHistSeriesRef.current = chart.addHistogramSeries({
        priceScaleId: "macd",
        priceLineVisible: false,
        lastValueVisible: false,
        visible: indicators.macd,
      } as HistogramSeriesOptions);

      macdLineSeriesRef.current = chart.addLineSeries({
        color: CHART_COLORS.macdLine,
        lineWidth: 1,
        priceScaleId: "macd",
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: indicators.macd,
      } as LineSeriesOptions);

      macdSignalSeriesRef.current = chart.addLineSeries({
        color: CHART_COLORS.macdSignal,
        lineWidth: 1,
        priceScaleId: "macd",
        priceLineVisible: false,
        lastValueVisible: false,
        crosshairMarkerVisible: false,
        visible: indicators.macd,
      } as LineSeriesOptions);

      chart.priceScale("macd").applyOptions({
        scaleMargins: { top: 0.78, bottom: 0.02 },
        autoScale: true,
      });

      // -- ResizeObserver --
      const observer = new ResizeObserver((entries) => {
        if (chart && entries[0]) {
          const { width } = entries[0].contentRect;
          chart.applyOptions({ width });
        }
      });
      observer.observe(containerRef.current!);
      observerRef.current = observer;

      chart.subscribeCrosshairMove((param) => {
        const visibleTrades = resolveVisibleTrades(
          tradesRef.current,
          showAllExecutionsRef.current,
          highlightedTradeIdRef.current,
        );
        const match = findTradeMarkerForTime(
          visibleTrades,
          (param as { time?: unknown } | undefined)?.time,
          highlightedTradeIdRef.current,
          barsRef.current,
        );
        const nextTradeId = match?.tradeId ?? null;
        if (hoveredMarkerIdRef.current !== nextTradeId) {
          hoveredMarkerIdRef.current = nextTradeId;
          onTradeHoverRef.current?.(nextTradeId);
        }
      });

      chart.subscribeClick((param) => {
        const visibleTrades = resolveVisibleTrades(
          tradesRef.current,
          showAllExecutionsRef.current,
          highlightedTradeIdRef.current,
        );
        const match = findTradeMarkerForTime(
          visibleTrades,
          (param as { time?: unknown } | undefined)?.time,
          highlightedTradeIdRef.current,
          barsRef.current,
        );
        if (match?.tradeId) {
          onTradeSelectRef.current?.(match.tradeId);
        }
      });

      // Fetch initial data
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
        sma20SeriesRef.current = null;
        sma50SeriesRef.current = null;
        ema9SeriesRef.current = null;
        vwapSeriesRef.current = null;
        rsiSeriesRef.current = null;
        macdLineSeriesRef.current = null;
        macdSignalSeriesRef.current = null;
        macdHistSeriesRef.current = null;
        priceLinesRef.current = [];
        rsiLinesRef.current = [];
      }
    };
    // Only re-init when height changes. Symbol/timeframe changes handled separately.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    chartRef.current?.applyOptions({ height: chartHeight });
  }, [chartHeight]);

  useEffect(() => {
    chartRef.current?.applyOptions({
      layout: {
        background: { color: chartTheme.background },
        textColor: chartTheme.text,
        fontFamily: "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, monospace",
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
  }, [chartTheme]);

  // ---------------------------------------------------------------------------
  // Re-fetch on symbol or timeframe change
  // ---------------------------------------------------------------------------

  useEffect(() => {
    // Wait for init to finish, then fetch
    if (initPromiseRef.current) {
      initPromiseRef.current.then(() => {
        if (chartRef.current) {
          fetchAndRender(timeframe);
        }
      });
    }
  }, [timeframe, symbol, fetchAndRender]);

  // ---------------------------------------------------------------------------
  // Fetch AI signals for heatmap
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!aiSignalsEnabled) {
      setAiSignals([]);
      return;
    }

    let cancelled = false;

    const fetchSignals = async () => {
      try {
        const res = await fetch(
          `/api/ai/tools/signals?symbol=${encodeURIComponent(symbol)}&timeframe=${timeframe}&limit=300`,
        );
        if (!res.ok) return;
        const payload = await res.json();
        if (!cancelled && Array.isArray(payload?.signals)) {
          setAiSignals(payload.signals as AISignal[]);
        }
      } catch {
        // silently fail -- heatmap is non-critical
      }
    };

    void fetchSignals();
    return () => { cancelled = true; };
  }, [symbol, timeframe, aiSignalsEnabled]);

  // ---------------------------------------------------------------------------
  // Track chart container dimensions for heatmap canvas sizing
  // ---------------------------------------------------------------------------

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const updateDims = () => {
      setChartDimensions({ width: el.clientWidth, height: el.clientHeight });
    };
    updateDims();

    const observer = new ResizeObserver(() => updateDims());
    observer.observe(el);
    return () => observer.disconnect();
  }, [chartHeight]);

  // ---------------------------------------------------------------------------
  // Toggle indicators visibility (bulk on/off from overlay settings)
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!indicatorsVisible) {
      sma20SeriesRef.current?.applyOptions({ visible: false });
      sma50SeriesRef.current?.applyOptions({ visible: false });
      ema9SeriesRef.current?.applyOptions({ visible: false });
      vwapSeriesRef.current?.applyOptions({ visible: false });
      rsiSeriesRef.current?.applyOptions({ visible: false });
      macdLineSeriesRef.current?.applyOptions({ visible: false });
      macdSignalSeriesRef.current?.applyOptions({ visible: false });
      macdHistSeriesRef.current?.applyOptions({ visible: false });
    } else {
      // Re-apply individual indicator states
      sma20SeriesRef.current?.applyOptions({ visible: indicators.sma20 });
      sma50SeriesRef.current?.applyOptions({ visible: indicators.sma50 });
      ema9SeriesRef.current?.applyOptions({ visible: indicators.ema9 });
      vwapSeriesRef.current?.applyOptions({ visible: indicators.vwap });
      rsiSeriesRef.current?.applyOptions({ visible: indicators.rsi });
      macdLineSeriesRef.current?.applyOptions({ visible: indicators.macd });
      macdSignalSeriesRef.current?.applyOptions({ visible: indicators.macd });
      macdHistSeriesRef.current?.applyOptions({ visible: indicators.macd });
    }
  }, [indicatorsVisible, indicators]);

  // ---------------------------------------------------------------------------
  // Trade markers visibility toggle
  // ---------------------------------------------------------------------------

  useEffect(() => {
    if (!candleSeriesRef.current) return;
    if (!tradeMarkersEnabled) {
      candleSeriesRef.current.setMarkers([]);
    } else if (barsRef.current.length > 0) {
      applyTradeMarkers(barsRef.current);
    }
  }, [tradeMarkersEnabled, applyTradeMarkers]);

  // ---------------------------------------------------------------------------
  // Quote display values
  // ---------------------------------------------------------------------------

  const lastPrice = quote?.price ?? quote?.last;
  const change = quote?.change;
  const changePct = quote?.change_pct;
  const isPositive = change != null ? change >= 0 : null;
  const companyName = quote?.name;

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="app-panel overflow-hidden p-4 sm:p-5">
      <div className="mb-4 flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <span className="text-sm font-mono font-bold">{symbol}</span>
          {companyName && (
            <span className="max-w-[240px] truncate text-xs text-muted-foreground">
              {companyName}
            </span>
          )}
          {lastPrice != null && (
            <span className="text-sm font-mono tabular-nums font-semibold">
              ${lastPrice.toFixed(2)}
            </span>
          )}
          {change != null && changePct != null && (
            <span
              className={`text-xs font-mono tabular-nums font-medium ${
                isPositive ? "text-emerald-400" : "text-red-400"
              }`}
            >
              {isPositive ? "+" : ""}
              {change.toFixed(2)} ({isPositive ? "+" : ""}
              {changePct.toFixed(2)}%)
            </span>
          )}
        </div>

        <div className="flex flex-col gap-3 xl:items-end">
          <label className="flex items-center gap-2 self-start cursor-pointer select-none xl:self-end">
            <input
              type="checkbox"
              checked={showAllExecutions}
              onChange={(e) => setShowAllExecutions(e.target.checked)}
              className="h-3.5 w-3.5 rounded border-border accent-blue-500 cursor-pointer"
            />
            <span className="text-[11px] text-muted-foreground whitespace-nowrap">
              Show all executions
            </span>
          </label>

          <div className="app-segmented">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`app-segment font-mono ${
                  timeframe === tf ? "app-toggle-active" : ""
                }`}
              >
                {tf}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-center gap-1.5">
        {ALL_INDICATORS.map((ind) => {
          const meta = INDICATOR_META[ind];
          return (
            <button
              key={ind}
              onClick={() => toggleIndicator(ind)}
              className={`app-toggle ${indicators[ind] ? "app-toggle-active" : ""}`}
            >
              <span className="flex items-center gap-1.5">
                <span
                  className="inline-block w-2 h-2 rounded-full flex-shrink-0"
                  style={{ backgroundColor: meta.color }}
                />
                {meta.label}
              </span>
            </button>
          );
        })}
        <div className="ml-auto">
          <ChartOverlaySettings
            heatmapConfig={heatmapConfig}
            onHeatmapConfigChange={setHeatmapConfig}
            aiSignalsEnabled={aiSignalsEnabled}
            onAiSignalsEnabledChange={setAiSignalsEnabled}
            tradeMarkersEnabled={tradeMarkersEnabled}
            onTradeMarkersEnabledChange={setTradeMarkersEnabled}
            indicatorsEnabled={indicatorsVisible}
            onIndicatorsEnabledChange={setIndicatorsVisible}
            theme={theme}
          />
        </div>
      </div>

      <div className="relative" style={{ height: chartHeight }}>
        <div ref={containerRef} className="absolute inset-0" />

        <HeatmapOverlay
          signals={aiSignals}
          config={heatmapConfig}
          chartApi={chartRef.current}
          candleSeries={candleSeriesRef.current}
          width={chartDimensions.width}
          height={chartDimensions.height}
          theme={theme}
        />

        {loading && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-background/80 backdrop-blur-sm">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
          </div>
        )}

        {error && !loading && (
          <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 bg-background/80 backdrop-blur-sm">
            <AlertTriangle className="h-5 w-5 text-muted-foreground/60" />
            <span className="text-sm font-semibold text-foreground">Chart data unavailable</span>
            <span className="max-w-sm text-center text-sm text-muted-foreground">
              {error}. The workspace is falling back to quote data while the chart feed refreshes.
            </span>
            <div className="flex flex-wrap items-center justify-center gap-2 text-xs text-muted-foreground">
              <span className="rounded-full border border-border/60 bg-muted/35 px-3 py-1.5">
                Last: {lastPrice != null ? `$${lastPrice.toFixed(2)}` : "—"}
              </span>
              <span className="rounded-full border border-border/60 bg-muted/35 px-3 py-1.5">
                High: {quote?.high != null ? `$${quote.high.toFixed(2)}` : "—"}
              </span>
              <span className="rounded-full border border-border/60 bg-muted/35 px-3 py-1.5">
                Low: {quote?.low != null ? `$${quote.low.toFixed(2)}` : "—"}
              </span>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={() => void fetchAndRender(timeframe)}>
              Retry Chart
            </Button>
          </div>
        )}
      </div>
    </div>
  );
}
