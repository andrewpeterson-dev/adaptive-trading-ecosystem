"use client";

import React, { useState, useMemo } from "react";
import { Clock } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";

type FilterTab = "all" | "buys" | "sells";

export function TradeHistoryPanel() {
  const { trades, loading } = useTradeStore();
  const [filter, setFilter] = useState<FilterTab>("all");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const filtered = useMemo(() => {
    const list = [...trades].sort((a: Record<string, unknown>, b: Record<string, unknown>) => {
      const ta = (a.filled_at as string) || (a.submitted_at as string) || (a.timestamp as string) || "";
      const tb = (b.filled_at as string) || (b.submitted_at as string) || (b.timestamp as string) || "";
      return tb.localeCompare(ta); // newest first
    });

    if (filter === "buys") {
      return list.filter((t: Record<string, unknown>) => {
        const dir = (t.direction as string) || "";
        return dir === "buy" || dir === "long";
      });
    }
    if (filter === "sells") {
      return list.filter((t: Record<string, unknown>) => {
        const dir = (t.direction as string) || "";
        return dir === "sell" || dir === "short";
      });
    }
    return list;
  }, [trades, filter]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const paged = filtered.slice(page * pageSize, (page + 1) * pageSize);

  // Reset page when filter changes
  const handleFilterChange = (tab: FilterTab) => {
    setFilter(tab);
    setPage(0);
  };

  const isLoading = loading && trades.length === 0;

  const tabs: { label: string; value: FilterTab }[] = [
    { label: "All", value: "all" },
    { label: "Buys", value: "buys" },
    { label: "Sells", value: "sells" },
  ];

  // Loading state
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Trade History</h3>
            <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
              --
            </span>
          </div>
        </div>
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              <th className="py-2 px-4">Date/Time</th>
              <th className="py-2 px-4">Symbol</th>
              <th className="py-2 px-4">Side</th>
              <th className="py-2 px-4">Type</th>
              <th className="py-2 px-4">Qty</th>
              <th className="py-2 px-4">Price</th>
              <th className="py-2 px-4">Status</th>
              <th className="py-2 px-4">P&L</th>
              <th className="py-2 px-4">Source</th>
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2, 3, 4].map((i) => (
              <tr key={i} className="border-b border-border/50">
                <td className="py-3 px-4"><div className="h-4 w-28 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-12 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-10 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-14 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-8 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-16 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-14 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-16 animate-pulse bg-muted rounded" /></td>
                <td className="py-3 px-4"><div className="h-4 w-14 animate-pulse bg-muted rounded" /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // Empty state
  if (trades.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold">Trade History</h3>
            <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
              0
            </span>
          </div>
        </div>
        <div className="py-12 flex flex-col items-center gap-3 text-center px-4">
          <div className="inline-flex items-center justify-center h-10 w-10 rounded-full bg-muted/50 border border-border/50">
            <Clock className="h-4 w-4 text-muted-foreground/50" />
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground">
              No trades yet
            </div>
            <div className="text-xs text-muted-foreground/60 mt-0.5">
              Executed trades will appear here
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
          <h3 className="text-sm font-semibold">Trade History</h3>
          <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
            {trades.length}
          </span>
        </div>
        <div className="flex items-center gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => handleFilterChange(tab.value)}
              className={`text-xs font-medium px-2.5 py-1 rounded transition-colors ${
                filter === tab.value
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              <th className="py-2 px-4">Date/Time</th>
              <th className="py-2 px-4">Symbol</th>
              <th className="py-2 px-4">Side</th>
              <th className="py-2 px-4">Type</th>
              <th className="py-2 px-4">Qty</th>
              <th className="py-2 px-4">Price</th>
              <th className="py-2 px-4">Status</th>
              <th className="py-2 px-4">P&L</th>
              <th className="py-2 px-4">Source</th>
            </tr>
          </thead>
          <tbody>
            {paged.map((t: Record<string, unknown>, i: number) => {
              const pnl = (t.pnl as number) ?? 0;
              const isProfit = pnl >= 0;
              const pnlColor = pnl !== 0
                ? isProfit
                  ? "text-emerald-400"
                  : "text-red-400"
                : "text-muted-foreground";

              const date =
                (t.filled_at as string) ||
                (t.submitted_at as string) ||
                (t.timestamp as string) ||
                "";

              const direction = (t.direction as string) || "";
              const isBuy = direction === "buy" || direction === "long";

              const status = (t.status as string) || "filled";
              const statusClass =
                status === "filled"
                  ? "text-emerald-400 bg-emerald-400/10"
                  : status === "rejected"
                  ? "text-red-400 bg-red-400/10"
                  : "text-yellow-400 bg-yellow-400/10";

              const source =
                (t.bot_name as string) ||
                (t.source as string) ||
                "Manual";

              const orderType = (t.order_type as string) || "\u2014";
              const quantity = t.quantity as number | undefined;
              const filledPrice = t.filled_price as number | undefined;
              const entryPrice = t.entry_price as number | undefined;
              const symbol = (t.symbol as string) || "\u2014";
              const tradeId = (t.id as string) || `${symbol}-${i}`;

              return (
                <tr
                  key={tradeId}
                  className="border-b border-border/50 hover:bg-muted/30 transition-colors"
                >
                  <td className="py-2.5 px-4 text-xs text-muted-foreground font-mono tabular-nums">
                    {date ? date.slice(0, 16).replace("T", " ") : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 font-mono font-semibold">
                    {symbol}
                  </td>
                  <td className="py-2.5 px-4">
                    <span
                      className={`text-xs font-medium ${
                        isBuy ? "text-emerald-400" : "text-red-400"
                      }`}
                    >
                      {isBuy ? "BUY" : "SELL"}
                    </span>
                  </td>
                  <td className="py-2.5 px-4 text-xs text-muted-foreground capitalize">
                    {orderType}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {quantity != null ? quantity : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 font-mono tabular-nums">
                    {filledPrice != null
                      ? `$${filledPrice.toFixed(2)}`
                      : entryPrice != null
                      ? `$${entryPrice.toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4">
                    <span
                      className={`text-xs font-medium px-1.5 py-0.5 rounded ${statusClass}`}
                    >
                      {status}
                    </span>
                  </td>
                  <td
                    className={`py-2.5 px-4 font-mono tabular-nums font-medium ${pnlColor}`}
                  >
                    {pnl !== 0
                      ? `${isProfit ? "+" : ""}$${pnl.toFixed(2)}`
                      : "\u2014"}
                  </td>
                  <td className="py-2.5 px-4 text-xs text-muted-foreground">
                    {source}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {totalPages > 1 && (
        <div className="px-4 py-2.5 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-2.5 py-1 rounded border border-border/50 hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-2.5 py-1 rounded border border-border/50 hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
