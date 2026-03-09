"use client";

import React, { useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  LayoutGrid,
  List,
  Plus,
  Activity,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { usePolling } from "@/hooks/usePolling";
import { QuoteCard } from "@/components/trading/QuoteCard";
import type { QuoteData } from "@/components/trading/QuoteCard";
import { WatchlistRow } from "@/components/trading/WatchlistRow";

const DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "AAPL", "TSLA", "NVDA"];

async function fetchQuotes(symbols: string[]): Promise<QuoteData[]> {
  try {
    const data = await apiFetch<any>(`/api/trading/quotes?symbols=${symbols.join(",")}`);
    return data.quotes || data || [];
  } catch {
    return [];
  }
}

async function fetchRegime(): Promise<string | null> {
  try {
    const data = await apiFetch<any>("/api/models/regime");
    return data.regime || data.current_regime || null;
  } catch {
    return null;
  }
}

export default function WatchlistPage() {
  const [symbols, setSymbols] = useState<string[]>(DEFAULT_SYMBOLS);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [addInput, setAddInput] = useState("");
  const [regime, setRegime] = useState<string | null>(null);

  const quoteFetcher = useCallback(() => fetchQuotes(symbols), [symbols]);

  const { data: quotes, loading, refresh } = usePolling<QuoteData[]>({
    fetcher: quoteFetcher,
    interval: 60000,
  });

  React.useEffect(() => {
    fetchRegime().then(setRegime);
  }, []);

  const addSymbol = () => {
    const sym = addInput.trim().toUpperCase();
    if (sym && !symbols.includes(sym)) {
      setSymbols([...symbols, sym]);
      setAddInput("");
    }
  };

  const removeSymbol = (sym: string) => {
    setSymbols(symbols.filter((s) => s !== sym));
  };

  const handleAddKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") addSymbol();
  };

  const regimeLabel =
    regime?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) || null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-lg font-semibold tracking-tight">Watchlist</h1>
          <p className="text-xs text-muted-foreground mt-0.5 font-mono">
            {symbols.length} symbol{symbols.length !== 1 ? "s" : ""} tracked
          </p>
        </div>
        <div className="flex items-center gap-2">
          {regimeLabel && (
            <div className="flex items-center gap-1.5 mr-1">
              <Activity className="h-3 w-3 text-muted-foreground" />
              <span className="text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-widest bg-primary/10 text-primary border border-primary/20">
                {regimeLabel}
              </span>
            </div>
          )}
          <button
            onClick={() => setView(view === "grid" ? "list" : "grid")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
          >
            {view === "grid" ? (
              <List className="h-3.5 w-3.5" />
            ) : (
              <LayoutGrid className="h-3.5 w-3.5" />
            )}
            {view === "grid" ? "List" : "Grid"}
          </button>
          <button
            onClick={refresh}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        </div>
      </div>

      {/* Add Symbol */}
      <div className="flex items-center gap-2">
        <input
          type="text"
          value={addInput}
          onChange={(e) => setAddInput(e.target.value.toUpperCase())}
          onKeyDown={handleAddKeyDown}
          placeholder="Add ticker…"
          className="px-3 py-2 rounded-lg bg-card border border-border/60 text-sm font-mono w-36 focus:outline-none focus:ring-2 focus:ring-primary/30 focus:border-primary/40 transition-all placeholder:text-muted-foreground/50"
        />
        <button
          onClick={addSymbol}
          disabled={!addInput.trim()}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-primary/10 text-primary text-xs font-semibold hover:bg-primary/20 border border-primary/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </button>
        {symbols.length > DEFAULT_SYMBOLS.length && (
          <button
            onClick={() => setSymbols(DEFAULT_SYMBOLS)}
            className="text-xs text-muted-foreground hover:text-foreground transition-colors ml-1"
          >
            Reset to defaults
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && !quotes && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {/* Grid View */}
      {quotes && view === "grid" && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {quotes.map((q) => (
            <QuoteCard key={q.symbol} quote={q} onRemove={removeSymbol} />
          ))}
        </div>
      )}

      {/* List View */}
      {quotes && view === "list" && (
        <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-border/50 bg-muted/20 text-[10px] text-muted-foreground uppercase tracking-widest">
                  <th className="py-2.5 px-4 font-semibold">Symbol</th>
                  <th className="py-2.5 px-4 font-semibold">Price</th>
                  <th className="py-2.5 px-4 font-semibold">Change</th>
                  <th className="py-2.5 px-4 font-semibold">%</th>
                  <th className="py-2.5 px-4 font-semibold">Volume</th>
                  <th className="py-2.5 px-4 font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {quotes.map((q, i) => (
                  <WatchlistRow
                    key={q.symbol}
                    quote={q}
                    onRemove={removeSymbol}
                  />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Empty */}
      {symbols.length === 0 && (
        <div className="text-center py-24 space-y-4">
          <div className="inline-flex items-center justify-center h-12 w-12 rounded-full bg-muted/50 border border-border/50 mx-auto">
            <Activity className="h-5 w-5 text-muted-foreground/50" />
          </div>
          <div>
            <h2 className="text-sm font-semibold">Watchlist empty</h2>
            <p className="text-xs text-muted-foreground mt-1">
              Add symbols above to start tracking market data.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
