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
    <div className="pointer-events-none absolute right-4 top-4 z-10 max-w-[320px] rounded-[22px] border border-white/15 bg-slate-950/88 p-4 text-white shadow-[0_28px_80px_-38px_rgba(15,23,42,0.9)] backdrop-blur-xl">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-400">
            Trade Marker Overlay
          </div>
          <div className="mt-1 text-sm font-semibold text-white">
            {trade ? `${trade.symbol} ${trade.side.toUpperCase()}` : "Hover a marker"}
          </div>
        </div>
        <div className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${
          hovered ? "bg-sky-400/15 text-sky-300" : "bg-white/10 text-slate-300"
        }`}>
          {hovered ? "Hover" : "Selection"}
        </div>
      </div>

      {trade ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
            <div>
              <div className="text-slate-400">Entry</div>
              <div className="mt-1 font-mono text-white">{formatCurrency(trade.entryPrice)}</div>
            </div>
            <div>
              <div className="text-slate-400">Exit</div>
              <div className="mt-1 font-mono text-white">{formatCurrency(trade.exitPrice)}</div>
            </div>
            <div>
              <div className="text-slate-400">Quantity</div>
              <div className="mt-1 font-mono text-white">{trade.quantity.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-slate-400">PnL</div>
              <div className={`mt-1 font-mono ${trade.netPnl != null && trade.netPnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                {formatCurrency(trade.netPnl)}
              </div>
            </div>
            <div>
              <div className="text-slate-400">Return</div>
              <div className="mt-1 font-mono text-white">{formatPercent(trade.returnPct, 1, true)}</div>
            </div>
            <div>
              <div className="text-slate-400">Opened</div>
              <div className="mt-1 text-white">{formatDateTime(trade.entryTs ?? trade.createdAt)}</div>
            </div>
          </div>

          {(trade.botExplanation || trade.reasons?.length) && (
            <div className="mt-4 rounded-2xl border border-white/10 bg-white/5 px-3 py-3 text-xs leading-5 text-slate-200">
              {trade.botExplanation || trade.reasons?.join("; ")}
            </div>
          )}
        </>
      ) : (
        <div className="mt-4 space-y-3 text-xs text-slate-300">
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
