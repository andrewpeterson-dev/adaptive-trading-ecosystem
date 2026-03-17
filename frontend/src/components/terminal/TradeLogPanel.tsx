"use client";
import { List } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import type { BotTrade } from "@/lib/cerberus-api";

const MAX_VISIBLE = 20;

interface TradeLogPanelProps {
  trades: BotTrade[];
  selectedTradeId: string | null;
  onSelectTrade: (trade: BotTrade) => void;
}

export function TradeLogPanel({ trades, selectedTradeId, onSelectTrade }: TradeLogPanelProps) {
  return (
    <TerminalPanel title="Trade Log" icon={<List className="h-3.5 w-3.5" />} accent="text-fuchsia-400" compact>
      <div className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/60 grid grid-cols-[50px_40px_65px_55px_55px] gap-1 px-1 pb-1.5 border-b border-border/30">
        <span>Symbol</span><span>Side</span><span>Entry</span><span>Status</span><span className="text-right">P&L</span>
      </div>
      {trades.length === 0 ? (
        <div className="py-6 text-center text-xs text-muted-foreground">No trades recorded</div>
      ) : (
        <>
          <div className="divide-y divide-border/20">
            {trades.slice(0, MAX_VISIBLE).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => onSelectTrade(t)}
                className={`grid grid-cols-[50px_40px_65px_55px_55px] gap-1 w-full text-left px-1 py-1.5 text-[11px] rounded transition-colors ${selectedTradeId === t.id ? "bg-sky-400/10" : "hover:bg-muted/20"}`}
              >
                <span className="font-semibold text-foreground">{t.symbol}</span>
                <span className={t.side === "buy" ? "text-emerald-400" : "text-rose-400"}>{t.side.toUpperCase()}</span>
                <span className="text-muted-foreground font-mono">${t.entryPrice?.toFixed(2) ?? "N/A"}</span>
                <span className="flex items-center gap-1">
                  <span className={`h-1.5 w-1.5 rounded-full ${t.status === "open" ? "bg-emerald-400" : "bg-muted-foreground/40"}`} />
                  <span className="text-muted-foreground">{t.status}</span>
                </span>
                <span className={`text-right font-mono ${(t.netPnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                  {t.netPnl != null ? `${t.netPnl >= 0 ? "+" : ""}${t.netPnl.toFixed(2)}` : "-"}
                </span>
              </button>
            ))}
          </div>
          {trades.length > MAX_VISIBLE && (
            <div className="text-center py-1.5 text-[10px] text-muted-foreground border-t border-border/20">
              Showing {MAX_VISIBLE} of {trades.length} trades
            </div>
          )}
        </>
      )}
    </TerminalPanel>
  );
}
