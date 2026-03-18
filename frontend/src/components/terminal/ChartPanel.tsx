"use client";

import { useMemo, useState, useEffect } from "react";
import { BarChart3, LineChart, TrendingUp } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { BotTradeChart } from "@/components/bots/BotTradeChart";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { BotTrade } from "@/lib/cerberus-api";

type ChartMode = "performance" | "symbol";

interface ChartPanelProps {
  symbol: string;
  trades: BotTrade[];
  selectedTrade: BotTrade | null;
  hoveredTrade: BotTrade | null;
  selectedTradeId: string | null;
  onHoverTrade: (id: string | null) => void;
  onSelectTrade: (id: string | null) => void;
  equityCurve?: Array<{ date: string; value: number }>;
  initialCapital?: number;
}

/**
 * Build a cumulative P&L equity curve client-side from the bot's trades.
 * Used as a fallback when the server-provided equityCurve is empty.
 */
function buildEquityCurveFromTrades(
  trades: BotTrade[],
  initialCapital: number,
): Array<{ date: string; value: number }> {
  if (trades.length === 0) {
    return [{ date: new Date().toISOString().slice(0, 10), value: initialCapital }];
  }

  const ordered = [...trades].sort((a, b) => {
    const tsA = a.exitTs ?? a.entryTs ?? a.createdAt ?? "";
    const tsB = b.exitTs ?? b.entryTs ?? b.createdAt ?? "";
    return tsA < tsB ? -1 : tsA > tsB ? 1 : 0;
  });

  let equity = initialCapital;
  const curve: Array<{ date: string; value: number }> = [];

  for (const trade of ordered) {
    equity += trade.netPnl ?? 0;
    const ts = trade.exitTs ?? trade.entryTs ?? trade.createdAt ?? new Date().toISOString();
    const dateStr = ts.length >= 10 ? ts.slice(0, 10) : ts;
    curve.push({ date: dateStr, value: Math.round(equity * 100) / 100 });
  }

  return curve;
}

export function ChartPanel({
  symbol,
  trades,
  selectedTrade,
  hoveredTrade,
  selectedTradeId,
  onHoverTrade,
  onSelectTrade,
  equityCurve,
  initialCapital,
}: ChartPanelProps) {
  const capital = initialCapital ?? 100000;

  // Default to performance view; switch to symbol view when a trade is selected
  const [chartMode, setChartMode] = useState<ChartMode>("performance");

  // Auto-switch to symbol chart when a trade is selected
  useEffect(() => {
    if (selectedTrade) {
      setChartMode("symbol");
    }
  }, [selectedTrade]);

  // Build effective equity curve: use server data if available, otherwise compute client-side
  const effectiveEquityCurve = useMemo(() => {
    if (equityCurve && equityCurve.length > 0) return equityCurve;
    return buildEquityCurveFromTrades(trades, capital);
  }, [equityCurve, trades, capital]);

  // Compute equity stats for compact header display
  const equityStats = useMemo(() => {
    if (effectiveEquityCurve.length === 0) return null;
    const startVal = capital;
    const endVal = effectiveEquityCurve[effectiveEquityCurve.length - 1]?.value ?? 0;
    const returnPct = startVal > 0 ? ((endVal - startVal) / startVal) * 100 : 0;
    return { endVal, returnPct };
  }, [effectiveEquityCurve, capital]);

  // Count open vs closed trades
  const tradeStats = useMemo(() => {
    const open = trades.filter((t) => t.status === "open").length;
    const closed = trades.length - open;
    return { open, closed, total: trades.length };
  }, [trades]);

  const title = chartMode === "performance"
    ? "Bot Performance"
    : `Chart — ${symbol}`;

  return (
    <TerminalPanel
      title={title}
      icon={<LineChart className="h-3.5 w-3.5" />}
      accent="text-sky-400"
      compact
      actions={
        <div className="flex items-center gap-2">
          {/* Chart mode toggle */}
          <div className="flex items-center rounded-full border border-border/40 bg-muted/20 p-0.5">
            <button
              type="button"
              onClick={() => setChartMode("performance")}
              className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold transition-colors ${
                chartMode === "performance"
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <TrendingUp className="h-2.5 w-2.5" />
              P&L
            </button>
            <button
              type="button"
              onClick={() => setChartMode("symbol")}
              className={`flex items-center gap-1 rounded-full px-2 py-0.5 text-[9px] font-semibold transition-colors ${
                chartMode === "symbol"
                  ? "bg-primary/15 text-primary"
                  : "text-muted-foreground hover:text-foreground"
              }`}
            >
              <BarChart3 className="h-2.5 w-2.5" />
              Symbol
            </button>
          </div>

          {/* Trade count pills */}
          <span className="rounded-full bg-muted/30 px-2 py-0.5 text-[9px] font-mono tabular-nums text-muted-foreground">
            {tradeStats.total} trade{tradeStats.total !== 1 ? "s" : ""}
          </span>
          {tradeStats.open > 0 && (
            <span className="rounded-full bg-emerald-400/10 px-2 py-0.5 text-[9px] font-mono tabular-nums text-emerald-400">
              {tradeStats.open} open
            </span>
          )}
          {/* Equity return pill */}
          {equityStats && (
            <span
              className={`rounded-full px-2 py-0.5 text-[9px] font-mono tabular-nums font-semibold ${
                equityStats.returnPct >= 0
                  ? "bg-emerald-400/10 text-emerald-400"
                  : "bg-rose-400/10 text-rose-400"
              }`}
            >
              {equityStats.returnPct >= 0 ? "+" : ""}
              {equityStats.returnPct.toFixed(1)}%
            </span>
          )}
        </div>
      }
    >
      <div className="space-y-3">
        {chartMode === "performance" ? (
          /* ── Performance / Equity Curve (default view) ─────────── */
          <div className="overflow-hidden rounded-xl border border-border/30 [&_.recharts-cartesian-grid]:opacity-30">
            <EquityCurveChart
              data={effectiveEquityCurve}
              initialCapital={capital}
              height={420}
              compact
            />
          </div>
        ) : (
          /* ── Symbol Price Chart with trade markers ─────────────── */
          <div className="overflow-hidden rounded-xl border border-border/30">
            <BotTradeChart
              symbol={symbol}
              trades={trades}
              selectedTrade={selectedTrade}
              hoveredTrade={hoveredTrade}
              highlightedTradeId={selectedTradeId}
              onHoverTrade={onHoverTrade}
              onSelectTrade={onSelectTrade}
            />
          </div>
        )}
      </div>
    </TerminalPanel>
  );
}
