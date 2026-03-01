"use client";

import React, { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface TradeEntry {
  id?: string;
  symbol: string;
  direction: string;
  quantity: number;
  entry_price?: number;
  exit_price?: number;
  filled_price?: number;
  pnl?: number;
  pnl_pct?: number;
  timestamp?: string;
  submitted_at?: string;
  filled_at?: string;
  status?: string;
}

interface TradeHistoryProps {
  trades: TradeEntry[];
}

type SortField = "timestamp" | "symbol" | "pnl";

export function TradeHistory({ trades }: TradeHistoryProps) {
  const [sortField, setSortField] = useState<SortField>("timestamp");
  const [sortAsc, setSortAsc] = useState(false);
  const [page, setPage] = useState(0);
  const pageSize = 15;

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false);
    }
  };

  const SortIcon = ({ field }: { field: SortField }) => {
    if (sortField !== field) return null;
    return sortAsc ? (
      <ChevronUp className="h-3 w-3 inline ml-0.5" />
    ) : (
      <ChevronDown className="h-3 w-3 inline ml-0.5" />
    );
  };

  const sorted = [...trades].sort((a, b) => {
    const dir = sortAsc ? 1 : -1;
    switch (sortField) {
      case "timestamp": {
        const ta = a.filled_at || a.submitted_at || a.timestamp || "";
        const tb = b.filled_at || b.submitted_at || b.timestamp || "";
        return ta < tb ? dir : ta > tb ? -dir : 0;
      }
      case "symbol":
        return dir * a.symbol.localeCompare(b.symbol);
      case "pnl":
        return dir * ((a.pnl ?? 0) - (b.pnl ?? 0));
      default:
        return 0;
    }
  });

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const paged = sorted.slice(page * pageSize, (page + 1) * pageSize);

  if (trades.length === 0) {
    return (
      <div className="rounded-lg border border-border/50 bg-card">
        <div className="px-4 py-3 border-b">
          <h3 className="text-sm font-semibold">Trade History</h3>
        </div>
        <div className="py-8 text-center text-muted-foreground text-sm">
          No trades yet
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-border/50 bg-card overflow-x-auto">
      <div className="px-4 py-3 border-b">
        <h3 className="text-sm font-semibold">
          Trade History
          <span className="text-muted-foreground font-normal ml-2">{trades.length}</span>
        </h3>
      </div>
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
            <th
              className="py-2 px-4 cursor-pointer hover:text-foreground"
              onClick={() => handleSort("timestamp")}
            >
              Date <SortIcon field="timestamp" />
            </th>
            <th
              className="py-2 px-4 cursor-pointer hover:text-foreground"
              onClick={() => handleSort("symbol")}
            >
              Symbol <SortIcon field="symbol" />
            </th>
            <th className="py-2 px-4">Direction</th>
            <th className="py-2 px-4">Qty</th>
            <th className="py-2 px-4">Price</th>
            <th className="py-2 px-4">Status</th>
            <th
              className="py-2 px-4 cursor-pointer hover:text-foreground"
              onClick={() => handleSort("pnl")}
            >
              P&L <SortIcon field="pnl" />
            </th>
          </tr>
        </thead>
        <tbody>
          {paged.map((t, i) => {
            const pnl = t.pnl ?? 0;
            const isUp = pnl >= 0;
            const date = t.filled_at || t.submitted_at || t.timestamp || "";
            return (
              <tr key={t.id || `${t.symbol}-${i}`} className="border-b border-border/50 hover:bg-muted/30 transition-colors">
                <td className="py-2 px-4 text-xs text-muted-foreground font-mono">
                  {date ? date.slice(0, 16).replace("T", " ") : "—"}
                </td>
                <td className="py-2 px-4 font-mono font-medium">{t.symbol}</td>
                <td className="py-2 px-4">
                  <span
                    className={`text-xs font-medium ${
                      t.direction === "long" ? "text-emerald-400" : "text-red-400"
                    }`}
                  >
                    {t.direction === "long" ? "BUY" : "SELL"}
                  </span>
                </td>
                <td className="py-2 px-4 font-mono">{t.quantity}</td>
                <td className="py-2 px-4 font-mono">
                  {t.filled_price ? `$${t.filled_price.toFixed(2)}` : t.entry_price ? `$${t.entry_price.toFixed(2)}` : "—"}
                </td>
                <td className="py-2 px-4">
                  <span
                    className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                      t.status === "filled"
                        ? "text-emerald-400 bg-emerald-400/10"
                        : t.status === "rejected"
                        ? "text-red-400 bg-red-400/10"
                        : "text-muted-foreground bg-muted"
                    }`}
                  >
                    {t.status || "filled"}
                  </span>
                </td>
                <td className={`py-2 px-4 font-mono font-medium ${isUp ? "text-emerald-400" : "text-red-400"}`}>
                  {pnl !== 0 ? `${isUp ? "+" : ""}$${pnl.toFixed(2)}` : "—"}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {totalPages > 1 && (
        <div className="px-4 py-2 border-t flex items-center justify-between text-xs text-muted-foreground">
          <span>
            Page {page + 1} of {totalPages}
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(Math.max(0, page - 1))}
              disabled={page === 0}
              className="px-2 py-1 rounded border hover:bg-muted disabled:opacity-30"
            >
              Prev
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
              disabled={page >= totalPages - 1}
              className="px-2 py-1 rounded border hover:bg-muted disabled:opacity-30"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
