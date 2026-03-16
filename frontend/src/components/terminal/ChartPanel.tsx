"use client";

import { useMemo } from "react";
import { LineChart, TrendingUp } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import { BotTradeChart } from "@/components/bots/BotTradeChart";
import { EquityCurveChart } from "@/components/charts/EquityCurveChart";
import type { BotTrade } from "@/lib/cerberus-api";
import { formatCurrency } from "@/lib/bot-visualization";

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
  // Compute equity stats for compact header display
  const equityStats = useMemo(() => {
    if (!equityCurve || equityCurve.length === 0) return null;
    const startVal = initialCapital ?? equityCurve[0]?.value ?? 0;
    const endVal = equityCurve[equityCurve.length - 1]?.value ?? 0;
    const returnPct = startVal > 0 ? ((endVal - startVal) / startVal) * 100 : 0;
    return { endVal, returnPct };
  }, [equityCurve, initialCapital]);

  // Count open vs closed trades
  const tradeStats = useMemo(() => {
    const open = trades.filter((t) => t.status === "open").length;
    const closed = trades.length - open;
    return { open, closed, total: trades.length };
  }, [trades]);

  return (
    <TerminalPanel
      title={`Chart — ${symbol}`}
      icon={<LineChart className="h-3.5 w-3.5" />}
      accent="text-sky-400"
      compact
      actions={
        <div className="flex items-center gap-2">
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
        {/* Main price chart with trade markers */}
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

        {/* Compact equity curve */}
        {equityCurve && equityCurve.length > 0 && (
          <div>
            <div className="mb-1.5 flex items-center gap-1.5">
              <TrendingUp className="h-3 w-3 text-muted-foreground/60" />
              <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                Equity Curve
              </span>
              {equityStats && (
                <span className="ml-auto text-[10px] font-mono tabular-nums text-muted-foreground">
                  {formatCurrency(equityStats.endVal)}
                </span>
              )}
            </div>
            <div className="overflow-hidden rounded-xl border border-border/30 [&_.recharts-cartesian-grid]:opacity-30">
              <EquityCurveChart
                data={equityCurve}
                initialCapital={initialCapital}
                height={120}
              />
            </div>
          </div>
        )}
      </div>
    </TerminalPanel>
  );
}
