"use client";

import type { BotTrade } from "@/lib/cerberus-api";
import {
  formatCurrency,
  formatDateTime,
  formatPercent,
} from "@/lib/bot-visualization";

interface TradeMarkerOverlayProps {
  trade: BotTrade | null;
  hovered: boolean;
}

export function TradeMarkerOverlay({
  trade,
  hovered,
}: TradeMarkerOverlayProps) {
  return (
    <div className="pointer-events-none absolute left-4 right-4 top-4 z-10 rounded-[22px] border border-border/60 bg-card p-4 shadow-[0_28px_80px_-38px_rgba(15,23,42,0.9)] backdrop-blur-xl sm:left-auto sm:max-w-[320px]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Trade Detail
          </div>
          <div className="mt-1 text-sm font-semibold text-foreground">
            {trade ? `${trade.symbol} ${trade.side.toUpperCase()}` : "Hover a marker"}
          </div>
        </div>
        <div className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${
          hovered ? "bg-primary/15 text-primary" : "bg-muted text-muted-foreground"
        }`}>
          {hovered ? "Hover" : "Selection"}
        </div>
      </div>

      {trade ? (
        <>
          <div className="mt-4 grid grid-cols-1 gap-3 text-xs sm:grid-cols-2">
            <div>
              <div className="text-muted-foreground">Entry</div>
              <div className="mt-1 font-mono text-foreground">{formatCurrency(trade.entryPrice)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Exit</div>
              <div className="mt-1 font-mono text-foreground">{formatCurrency(trade.exitPrice)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Quantity</div>
              <div className="mt-1 font-mono text-foreground">{trade.quantity.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">PnL</div>
              <div className={`mt-1 font-mono ${trade.netPnl != null && trade.netPnl >= 0 ? "text-emerald-500 dark:text-emerald-300" : "text-rose-500 dark:text-rose-300"}`}>
                {formatCurrency(trade.netPnl)}
              </div>
            </div>
            <div>
              <div className="text-muted-foreground">Return</div>
              <div className="mt-1 font-mono text-foreground">{formatPercent(trade.returnPct, 1, true)}</div>
            </div>
            <div>
              <div className="text-muted-foreground">Opened</div>
              <div className="mt-1 text-foreground">{formatDateTime(trade.entryTs ?? trade.createdAt)}</div>
            </div>
          </div>

          {(trade.botExplanation || trade.reasons?.length) && (
            <div className="mt-4 rounded-2xl border border-border/60 bg-muted/30 px-3 py-3 text-xs leading-5 text-foreground">
              {trade.botExplanation || trade.reasons?.join("; ")}
            </div>
          )}
        </>
      ) : (
        <div className="mt-4 space-y-3 text-xs text-muted-foreground">
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-400" />
            Entry marker
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-sky-400" />
            Exit marker
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-400" />
            Stop loss / losing exit
          </div>
          <div className="flex items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full bg-teal-400" />
            Take profit line
          </div>
        </div>
      )}
    </div>
  );
}
