"use client";
import { Crosshair } from "lucide-react";
import { TerminalPanel } from "./TerminalPanel";
import type { BotPerformanceSummary } from "@/lib/cerberus-api";

interface OpenPositionsPanelProps {
  performance: BotPerformanceSummary;
  onSelectSymbol?: (symbol: string) => void;
}

export function OpenPositionsPanel({ performance, onSelectSymbol }: OpenPositionsPanelProps) {
  const positions = performance.open_positions ?? [];

  return (
    <TerminalPanel title="Open Positions" icon={<Crosshair className="h-3.5 w-3.5" />} accent="text-emerald-400" compact>
      {positions.length === 0 ? (
        <div className="flex items-center justify-center h-full text-sm text-muted-foreground">No open positions</div>
      ) : (
        <div className="space-y-1">
          <div className="grid grid-cols-[1fr_70px_70px_60px] gap-1 text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/60 px-1 pb-1">
            <span>Symbol</span><span className="text-right">Entry</span><span className="text-right">Current</span><span className="text-right">P&L</span>
          </div>
          {positions.map((p) => (
            <button
              key={p.symbol}
              type="button"
              onClick={() => onSelectSymbol?.(p.symbol)}
              className="grid grid-cols-[1fr_70px_70px_60px] gap-1 w-full rounded-lg px-1 py-1.5 text-xs hover:bg-muted/30 transition-colors text-left"
            >
              <span className="font-semibold text-foreground">{p.symbol}</span>
              <span className="text-right text-muted-foreground font-mono">${p.entryPrice.toFixed(2)}</span>
              <span className="text-right text-muted-foreground font-mono">${p.currentPrice.toFixed(2)}</span>
              <span className={`text-right font-mono font-semibold ${p.unrealizedPnl >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                {p.unrealizedPnl >= 0 ? "+" : ""}{p.unrealizedPnl.toFixed(2)}
              </span>
            </button>
          ))}
        </div>
      )}
    </TerminalPanel>
  );
}
