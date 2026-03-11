"use client";

import type { BotTrade } from "@/lib/cerberus-api";
import {
  formatCurrency,
  formatDateLabel,
  formatPercent,
  formatTimeLabel,
  humanizeLabel,
} from "@/lib/bot-visualization";

interface TradeHistoryTableProps {
  trades: BotTrade[];
  selectedTradeId: string | null;
  onSelectTrade: (trade: BotTrade) => void;
}

function signalLabel(trade: BotTrade): string {
  if (trade.reasons && trade.reasons.length > 0) {
    return trade.reasons[0];
  }
  if (trade.botExplanation) {
    return trade.botExplanation;
  }
  if (trade.strategyTag) {
    return humanizeLabel(trade.strategyTag);
  }
  return "No trigger narrative recorded";
}

export function TradeHistoryTable({
  trades,
  selectedTradeId,
  onSelectTrade,
}: TradeHistoryTableProps) {
  return (
    <section className="app-panel overflow-hidden">
      <div className="border-b border-border/60 px-5 py-4 sm:px-6">
        <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
          Trade History Panel
        </div>
        <h3 className="mt-1 text-lg font-semibold text-foreground">Structured execution log</h3>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full border-separate border-spacing-0 text-sm">
          <thead>
            <tr className="bg-muted/15 text-left">
              {["Date", "Time", "Asset", "Action", "Price", "Quantity", "PnL", "Signal"].map((header) => (
                <th
                  key={header}
                  className="border-b border-border/60 px-4 py-3 text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground"
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-8 text-center text-sm text-muted-foreground">
                  No trades match the current timeline and symbol filters.
                </td>
              </tr>
            ) : (
              trades.map((trade) => {
                const active = selectedTradeId === trade.id;
                const pnl = trade.netPnl ?? 0;
                return (
                  <tr
                    key={trade.id}
                    onClick={() => onSelectTrade(trade)}
                    className={`cursor-pointer border-b border-border/40 transition-colors ${
                      active ? "bg-sky-400/8" : "hover:bg-muted/10"
                    }`}
                  >
                    <td className="px-4 py-3 text-foreground">{formatDateLabel(trade.entryTs ?? trade.createdAt)}</td>
                    <td className="px-4 py-3 text-muted-foreground">{formatTimeLabel(trade.entryTs ?? trade.createdAt)}</td>
                    <td className="px-4 py-3 font-semibold text-foreground">{trade.symbol}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`rounded-full px-2.5 py-1 text-[11px] font-semibold tracking-[0.16em] ${
                          trade.side.toLowerCase().startsWith("sell")
                            ? "bg-orange-500/10 text-orange-400"
                            : "bg-emerald-500/10 text-emerald-400"
                        }`}
                      >
                        {trade.side.toUpperCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 font-mono text-foreground">{formatCurrency(trade.entryPrice)}</td>
                    <td className="px-4 py-3 font-mono text-foreground">{trade.quantity.toFixed(2)}</td>
                    <td className={`px-4 py-3 font-mono ${pnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                      {formatCurrency(trade.netPnl)}
                      {trade.returnPct != null && (
                        <span className="ml-2 text-[11px] text-muted-foreground">
                          {formatPercent(trade.returnPct, 1, true)}
                        </span>
                      )}
                    </td>
                    <td className="max-w-[340px] px-4 py-3 text-muted-foreground">
                      <div className="max-h-10 overflow-hidden leading-5">{signalLabel(trade)}</div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
