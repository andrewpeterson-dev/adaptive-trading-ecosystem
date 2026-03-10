"use client";

import React, { useState } from "react";
import { Loader2, TrendingUp, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradeStore } from "@/stores/trade-store";

interface PositionsPanelProps {
  onClose: () => void;
}

export function PositionsPanel({ onClose }: PositionsPanelProps) {
  const { positions, loading } = useTradeStore();
  const [closingSymbol, setClosingSymbol] = useState<string | null>(null);

  const handleClosePosition = async (position: {
    symbol: string;
    side: string;
    quantity: number;
    current_price: number;
  }) => {
    setClosingSymbol(position.symbol);
    try {
      await apiFetch("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol: position.symbol,
          direction: position.side === "long" ? "short" : "long",
          quantity: Math.abs(position.quantity),
          strength: 1.0,
          model_name: "manual",
          order_type: "market",
          limit_price: position.current_price,
          user_confirmed: true,
        }),
      });
      onClose();
    } catch {
      // silent — refresh will reflect actual state
    } finally {
      setClosingSymbol(null);
    }
  };

  const isLoading = loading && positions.length === 0;

  // Loading state
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Open Positions</h3>
            <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
              --
            </span>
          </div>
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              <th className="py-2 px-4">Symbol</th>
              <th className="py-2 px-4">Qty</th>
              <th className="py-2 px-4">Avg Entry</th>
              <th className="py-2 px-4">Current</th>
              <th className="py-2 px-4">Mkt Value</th>
              <th className="py-2 px-4">P&L ($)</th>
              <th className="py-2 px-4">P&L (%)</th>
              <th className="py-2 px-4">Side</th>
              <th className="py-2 px-4">Source</th>
              <th className="py-2 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2].map((i) => (
              <tr key={i} className="border-b border-border/50">
                <td className="py-3 px-4"><div className="h-4 w-12 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-8 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-16 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-16 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-20 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-16 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-12 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-10 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-14 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-12 animate-pulse bg-muted rounded" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // Empty state
  if (positions.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Open Positions</h3>
            <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
              0
            </span>
          </div>
        </div>
        <div className="py-12 flex flex-col items-center gap-3 text-center px-4">
          <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-muted/50 border border-border/50">
            <TrendingUp className="h-4 w-4 text-muted-foreground/50" />
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground">
              No open positions
            </div>
            <div className="text-xs text-muted-foreground/60 mt-0.5">
              Place an order to open a position
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
      <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold">Open Positions</h3>
          <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
            {positions.length}
          </span>
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              <th className="py-2 px-4">Symbol</th>
              <th className="py-2 px-4">Qty</th>
              <th className="py-2 px-4">Avg Entry</th>
              <th className="py-2 px-4">Current</th>
              <th className="py-2 px-4">Mkt Value</th>
              <th className="py-2 px-4">P&L ($)</th>
              <th className="py-2 px-4">P&L (%)</th>
              <th className="py-2 px-4">Side</th>
              <th className="py-2 px-4">Source</th>
              <th className="py-2 px-4"></th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => {
              const pnl = p.unrealized_pnl ?? 0;
              const pnlPct = p.unrealized_pnl_pct ?? 0;
              const isProfit = pnl >= 0;
              const pnlColor = isProfit ? "text-emerald-400" : "text-red-400";
              const pos = p as unknown as Record<string, unknown>;
              const source =
                (pos.bot_name as string) ||
                (pos.source as string) ||
                "Manual";

              return (
                <tr
                  key={p.symbol}
                  className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <td className="py-2.5 px-4 font-mono font-semibold text-sm">
                    {p.symbol}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {p.quantity != null ? p.quantity : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {p.avg_entry_price != null
                      ? `$${p.avg_entry_price.toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {p.current_price != null
                      ? `$${p.current_price.toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {p.market_value != null
                      ? `$${p.market_value.toLocaleString("en-US", {
                          minimumFractionDigits: 2,
                          maximumFractionDigits: 2,
                        })}`
                      : "\u2014"}
                  </td>
                  <td
                    className={`py-2.5 px-4 font-mono tabular-nums font-medium ${pnlColor}`}
                  >
                    {pnl !== 0 || p.unrealized_pnl != null
                      ? `${isProfit ? "+" : ""}$${pnl.toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td
                    className={`py-2.5 px-4 font-mono tabular-nums font-medium ${pnlColor}`}
                  >
                    {pnlPct !== 0 || p.unrealized_pnl_pct != null
                      ? `${isProfit ? "+" : ""}${(pnlPct * 100).toFixed(1)}%`
                      : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4">
                    <span
                      className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                        p.side === "long"
                          ? "text-emerald-400 bg-emerald-400/10"
                          : "text-red-400 bg-red-400/10"
                      }`}
                    >
                      {p.side?.toUpperCase() || "\u2014"}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-xs text-muted-foreground">
                    {source}
                  </td>
                  <td className="py-2.5 px-4">
                    <button
                      onClick={() => handleClosePosition(p)}
                      disabled={closingSymbol === p.symbol}
                      className="text-xs text-muted-foreground hover:text-foreground border border-transparent hover:border-border/50 rounded-md px-2 py-1 transition-colors flex items-center gap-1 disabled:opacity-40"
                    >
                      {closingSymbol === p.symbol ? (
                        <Loader2 className="h-3 w-3 animate-spin" />
                      ) : (
                        <X className="h-3 w-3" />
                      )}
                      Close
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
