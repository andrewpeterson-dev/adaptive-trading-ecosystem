import type { BotDetail, BotTrade } from "@/lib/cerberus-api";
import type { PriceLevelLine, TradeMarker } from "@/types/chart";

export type TimelineGranularity = "day" | "week" | "month";

export interface StrategyConditionLike {
  indicator?: string;
  operator?: string;
  value?: number | string | null;
  params?: Record<string, number>;
  field?: string;
  compare_to?: string;
  action?: string;
  signal?: string;
  logic?: string;
}

export interface ConditionGroupLike {
  id?: string;
  label?: string;
  conditions?: StrategyConditionLike[];
}

export interface TimelineBucket {
  key: string;
  label: string;
  startMs: number;
  endMs: number;
  tradeCount: number;
  winCount: number;
  totalNetPnl: number;
  trades: BotTrade[];
}

export interface BotStatsSnapshot {
  totalReturnPct: number;
  winRatePct: number;
  sharpeRatio: number;
  averageTradeReturnPct: number;
  maxDrawdownPct: number;
  tradeCount: number;
  profitFactor: number | null;
  totalNetPnl: number;
}

const DAY_MS = 24 * 60 * 60 * 1000;

export function getBotConfig(detail: BotDetail | null | undefined): Record<string, unknown> {
  return (detail?.config ?? {}) as Record<string, unknown>;
}

export function getTradeTimestampMs(trade: BotTrade): number | null {
  const raw = trade.entryTs ?? trade.createdAt ?? trade.exitTs;
  if (!raw) return null;
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getTradeExitTimestampMs(trade: BotTrade): number | null {
  if (!trade.exitTs) return null;
  const parsed = Date.parse(trade.exitTs);
  return Number.isFinite(parsed) ? parsed : null;
}

export function getTradeById(trades: BotTrade[], tradeId: string | null | undefined): BotTrade | null {
  if (!tradeId) return null;
  return trades.find((trade) => trade.id === tradeId) ?? null;
}

export function formatCurrency(value: number | null | undefined, digits = 2): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  }).format(value);
}

export function formatCompactCurrency(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatPercent(
  value: number | null | undefined,
  digits = 1,
  fraction = true,
): string {
  if (value == null || !Number.isFinite(value)) return "N/A";
  const pctValue = fraction ? value * 100 : value;
  return `${pctValue.toFixed(digits)}%`;
}

export function formatProbability(value: number | null | undefined): string {
  if (value == null || !Number.isFinite(value)) return "Not captured";
  return formatPercent(value, 0, true);
}

export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "N/A";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatDateLabel(value: string | null | undefined): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "N/A";
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
  }).format(date);
}

export function formatTimeLabel(value: string | null | undefined): string {
  if (!value) return "N/A";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "N/A";
  return new Intl.DateTimeFormat("en-US", {
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

export function formatTimeframe(value: unknown): string {
  const raw = typeof value === "string" ? value : "";
  if (!raw) return "Not set";
  const lookup: Record<string, string> = {
    "1m": "1 minute",
    "5m": "5 minutes",
    "15m": "15 minutes",
    "1H": "1 hour",
    "4H": "4 hours",
    "1D": "1 day",
    "1W": "1 week",
  };
  return lookup[raw] ?? raw;
}

export function humanizeLabel(value: string | null | undefined): string {
  if (!value) return "N/A";
  return value
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase());
}

export function readNumber(value: unknown): number | null {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function summarizeRisk(config: Record<string, unknown>): string {
  const positionSize = readNumber(config.position_size_pct);
  const stopLoss = readNumber(config.stop_loss_pct);
  const maxExposure = readNumber(config.max_exposure_pct);

  const score =
    (positionSize && positionSize >= 0.15 ? 2 : positionSize && positionSize >= 0.08 ? 1 : 0) +
    (stopLoss && stopLoss >= 0.03 ? 2 : stopLoss && stopLoss >= 0.015 ? 1 : 0) +
    (maxExposure && maxExposure >= 0.75 ? 2 : maxExposure && maxExposure >= 0.4 ? 1 : 0);

  if (score <= 2) return "Conservative";
  if (score <= 4) return "Balanced";
  return "Aggressive";
}

export function getTrackedSymbols(detail: BotDetail): string[] {
  const config = getBotConfig(detail);
  const configured = Array.isArray(config.symbols) ? config.symbols : [];
  const symbols = configured
    .filter((symbol): symbol is string => typeof symbol === "string" && symbol.trim().length > 0)
    .map((symbol) => symbol.toUpperCase());

  for (const trade of detail.trades) {
    const symbol = trade.symbol?.toUpperCase();
    if (symbol && !symbols.includes(symbol)) {
      symbols.push(symbol);
    }
  }

  return symbols.length > 0 ? symbols : [detail.primarySymbol || "SPY"];
}

export function buildTradeMarkers(trades: BotTrade[]): TradeMarker[] {
  const markers: TradeMarker[] = [];

  for (const trade of trades) {
    const entryTime = getTradeTimestampMs(trade);
    if (entryTime != null && trade.entryPrice != null) {
      const isSellEntry = trade.side.toLowerCase().startsWith("sell");
      markers.push({
        time: Math.floor(entryTime / 1000),
        price: trade.entryPrice,
        side: isSellEntry ? "sell" : "buy",
        tradeId: trade.id,
        kind: "entry",
        label: `${isSellEntry ? "SELL" : "BUY"} ${trade.symbol}`,
        color: isSellEntry ? "#f97316" : "#22c55e",
        shape: isSellEntry ? "arrowDown" : "arrowUp",
        position: isSellEntry ? "aboveBar" : "belowBar",
        text: isSellEntry ? "SE" : "BE",
      });
    }

    const exitTime = getTradeExitTimestampMs(trade);
    if (exitTime != null && trade.exitPrice != null) {
      const pnl = trade.netPnl ?? 0;
      markers.push({
        time: Math.floor(exitTime / 1000),
        price: trade.exitPrice,
        side: trade.side.toLowerCase().startsWith("sell") ? "buy" : "sell",
        tradeId: trade.id,
        kind: "exit",
        label: `EXIT ${trade.symbol}`,
        color: pnl >= 0 ? "#38bdf8" : "#f43f5e",
        shape: "square",
        position: pnl >= 0 ? "aboveBar" : "belowBar",
        text: pnl >= 0 ? "TP" : "SL",
      });
    }
  }

  return markers.sort((left, right) => Number(left.time) - Number(right.time));
}

export function buildTradePriceLevels(trade: BotTrade | null): PriceLevelLine[] {
  if (!trade) return [];

  const levels: PriceLevelLine[] = [];
  if (trade.entryPrice != null) {
    levels.push({
      price: trade.entryPrice,
      color: "#22c55e",
      label: "Entry",
      lineStyle: 2,
    });
  }
  if (trade.exitPrice != null) {
    levels.push({
      price: trade.exitPrice,
      color: trade.netPnl != null && trade.netPnl >= 0 ? "#38bdf8" : "#f43f5e",
      label: "Exit",
      lineStyle: 2,
    });
  }
  if (trade.stopLossPrice != null) {
    levels.push({
      price: trade.stopLossPrice,
      color: "#ef4444",
      label: "Stop Loss",
      lineStyle: 1,
    });
  }
  if (trade.takeProfitPrice != null) {
    levels.push({
      price: trade.takeProfitPrice,
      color: "#14b8a6",
      label: "Take Profit",
      lineStyle: 1,
    });
  }
  return levels;
}

export function computeBotStats(detail: BotDetail, initialCapital = 100000): BotStatsSnapshot {
  const positivePnl = detail.trades
    .map((trade) => trade.netPnl ?? 0)
    .filter((value) => value > 0)
    .reduce((sum, value) => sum + value, 0);
  const negativePnl = Math.abs(
    detail.trades
      .map((trade) => trade.netPnl ?? 0)
      .filter((value) => value < 0)
      .reduce((sum, value) => sum + value, 0),
  );

  return {
    totalReturnPct: initialCapital > 0 ? (detail.performance.total_net_pnl / initialCapital) * 100 : 0,
    winRatePct: detail.performance.win_rate * 100,
    sharpeRatio: detail.performance.sharpe_ratio,
    averageTradeReturnPct: detail.performance.avg_return_pct * 100,
    maxDrawdownPct: detail.performance.max_drawdown * 100,
    tradeCount: detail.performance.trade_count,
    profitFactor: negativePnl > 0 ? positivePnl / negativePnl : positivePnl > 0 ? Number.POSITIVE_INFINITY : null,
    totalNetPnl: detail.performance.total_net_pnl,
  };
}

export function buildTimelineBuckets(
  trades: BotTrade[],
  granularity: TimelineGranularity,
): TimelineBucket[] {
  const buckets = new Map<string, TimelineBucket>();

  for (const trade of trades) {
    const timestampMs = getTradeTimestampMs(trade);
    if (timestampMs == null) continue;

    const bucketDate = new Date(timestampMs);
    let key = "";
    let label = "";
    let startMs = timestampMs;
    let endMs = timestampMs;

    if (granularity === "day") {
      const day = new Date(bucketDate.getFullYear(), bucketDate.getMonth(), bucketDate.getDate());
      startMs = day.getTime();
      endMs = startMs + DAY_MS - 1;
      key = day.toISOString().slice(0, 10);
      label = day.toLocaleDateString("en-US", { month: "short", day: "numeric" });
    } else if (granularity === "week") {
      const weekday = bucketDate.getDay();
      const mondayOffset = weekday === 0 ? -6 : 1 - weekday;
      const weekStart = new Date(bucketDate);
      weekStart.setDate(bucketDate.getDate() + mondayOffset);
      weekStart.setHours(0, 0, 0, 0);
      startMs = weekStart.getTime();
      endMs = startMs + DAY_MS * 7 - 1;
      key = `week-${weekStart.toISOString().slice(0, 10)}`;
      label = `Week of ${weekStart.toLocaleDateString("en-US", { month: "short", day: "numeric" })}`;
    } else {
      const monthStart = new Date(bucketDate.getFullYear(), bucketDate.getMonth(), 1);
      const monthEnd = new Date(bucketDate.getFullYear(), bucketDate.getMonth() + 1, 0, 23, 59, 59, 999);
      startMs = monthStart.getTime();
      endMs = monthEnd.getTime();
      key = `${bucketDate.getFullYear()}-${String(bucketDate.getMonth() + 1).padStart(2, "0")}`;
      label = monthStart.toLocaleDateString("en-US", { month: "short", year: "numeric" });
    }

    const existing = buckets.get(key);
    if (existing) {
      existing.tradeCount += 1;
      existing.winCount += trade.netPnl != null && trade.netPnl > 0 ? 1 : 0;
      existing.totalNetPnl += trade.netPnl ?? 0;
      existing.trades.push(trade);
    } else {
      buckets.set(key, {
        key,
        label,
        startMs,
        endMs,
        tradeCount: 1,
        winCount: trade.netPnl != null && trade.netPnl > 0 ? 1 : 0,
        totalNetPnl: trade.netPnl ?? 0,
        trades: [trade],
      });
    }
  }

  return Array.from(buckets.values()).sort((left, right) => left.startMs - right.startMs);
}

export function filterTradesBySymbol(trades: BotTrade[], symbol: string): BotTrade[] {
  return trades.filter((trade) => trade.symbol.toUpperCase() === symbol.toUpperCase());
}

export function filterTradesUntil(trades: BotTrade[], endMs: number | null): BotTrade[] {
  if (endMs == null) return trades;
  return trades.filter((trade) => {
    const timestampMs = getTradeTimestampMs(trade);
    return timestampMs != null && timestampMs <= endMs;
  });
}

export function getConditionGroups(config: Record<string, unknown>): ConditionGroupLike[] {
  const rawGroups = Array.isArray(config.condition_groups) ? config.condition_groups : [];
  return rawGroups.filter((group): group is ConditionGroupLike => typeof group === "object" && group !== null);
}

export function getExitConditions(config: Record<string, unknown>): StrategyConditionLike[] {
  const aiContext = (config.ai_context ?? {}) as Record<string, unknown>;
  const rawExit = Array.isArray(aiContext.exit_conditions) ? aiContext.exit_conditions : [];
  return rawExit.filter(
    (condition): condition is StrategyConditionLike => typeof condition === "object" && condition !== null,
  );
}

export function describeCondition(condition: StrategyConditionLike): string {
  const indicator = humanizeLabel(condition.indicator ?? "signal");
  const operatorMap: Record<string, string> = {
    ">": ">",
    "<": "<",
    ">=": ">=",
    "<=": "<=",
    "==": "=",
    crosses_above: "crosses above",
    crosses_below: "crosses below",
  };
  const operator = operatorMap[String(condition.operator ?? "")] ?? String(condition.operator ?? "");
  const target = condition.compare_to ? humanizeLabel(condition.compare_to) : String(condition.value ?? "");
  return `${indicator} ${operator} ${target}`.trim();
}

export function formatConditionParams(condition: StrategyConditionLike): string[] {
  const params = condition.params ?? {};
  return Object.entries(params).map(([key, value]) => `${key} ${value}`);
}

export function getAiOverview(detail: BotDetail): string {
  const config = getBotConfig(detail);
  const aiContext = (config.ai_context ?? {}) as Record<string, unknown>;
  const overview = typeof aiContext.overview === "string" ? aiContext.overview : null;
  return overview || detail.overview || "No AI reasoning summary available.";
}
