"use client";

import React, { useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  LayoutGrid,
  List,
  Plus,
  Activity,
  X,
} from "lucide-react";
import { usePolling } from "@/hooks/usePolling";
import { QuoteCard } from "@/components/trading/QuoteCard";
import type { QuoteData } from "@/components/trading/QuoteCard";
import { WatchlistRow } from "@/components/trading/WatchlistRow";

const DEFAULT_SYMBOLS = ["SPY", "QQQ", "IWM", "AAPL", "TSLA", "NVDA"];

async function fetchQuotes(symbols: string[]): Promise<QuoteData[]> {
  try {
    const token = typeof window !== "undefined"
      ? (document.cookie.match(/(?:^|; )auth_token=([^;]*)/)?.[1] || localStorage.getItem("auth_token"))
      : null;

    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch(
      `/api/trading/quotes?symbols=${symbols.join(",")}`,
      { headers }
    );
    if (res.ok) {
      const data = await res.json();
      return data.quotes || data || [];
    }
  } catch {
    // endpoint unavailable
  }
  return [];
}

async function fetchRegime(): Promise<string | null> {
  try {
    const token = typeof window !== "undefined"
      ? (document.cookie.match(/(?:^|; )auth_token=([^;]*)/)?.[1] || localStorage.getItem("auth_token"))
      : null;
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;

    const res = await fetch("/api/models/regime", { headers });
    if (res.ok) {
      const data = await res.json();
      return data.regime || data.current_regime || null;
    }
  } catch {
    // silent
  }
  return null;
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

  // Fetch regime once
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
    regime?.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()) ||
    null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Watchlist</h2>
          <p className="text-sm text-muted-foreground mt-0.5">
            {symbols.length} symbol{symbols.length !== 1 ? "s" : ""} tracked
          </p>
        </div>
        <div className="flex items-center gap-2">
          {regimeLabel && (
            <div className="flex items-center gap-1.5 mr-3">
              <Activity className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
                {regimeLabel}
              </span>
            </div>
          )}
          <button
            onClick={() => setView(view === "grid" ? "list" : "grid")}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
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
            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm text-muted-foreground hover:text-foreground hover:bg-muted/50 border border-border/50 transition-colors"
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
          placeholder="Add symbol..."
          className="px-3 py-2 rounded-md bg-background border border-border/50 text-sm font-mono w-40 focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
        />
        <button
          onClick={addSymbol}
          disabled={!addInput.trim()}
          className="inline-flex items-center gap-1.5 px-3 py-2 rounded-md bg-primary/10 text-primary text-sm font-medium hover:bg-primary/20 border border-primary/20 transition-colors disabled:opacity-30"
        >
          <Plus className="h-3.5 w-3.5" />
          Add
        </button>
        {symbols.length > DEFAULT_SYMBOLS.length && (
          <button
            onClick={() => setSymbols(DEFAULT_SYMBOLS)}
            className="text-xs text-muted-foreground hover:text-foreground ml-2"
          >
            Reset to defaults
          </button>
        )}
      </div>

      {/* Loading */}
      {loading && !quotes && (
        <div className="flex items-center justify-center py-20">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
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
        <div className="rounded-lg border border-border/50 bg-card overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
                <th className="py-2 px-4">Symbol</th>
                <th className="py-2 px-4">Price</th>
                <th className="py-2 px-4">Change</th>
                <th className="py-2 px-4">%</th>
                <th className="py-2 px-4">Volume</th>
                <th className="py-2 px-4"></th>
              </tr>
            </thead>
            <tbody>
              {quotes.map((q) => (
                <WatchlistRow
                  key={q.symbol}
                  quote={q}
                  onRemove={removeSymbol}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Empty */}
      {symbols.length === 0 && (
        <div className="text-center py-20 space-y-3">
          <Activity className="h-10 w-10 text-muted-foreground/40 mx-auto" />
          <h2 className="text-lg font-semibold">Watchlist Empty</h2>
          <p className="text-sm text-muted-foreground max-w-md mx-auto">
            Add symbols above to start tracking market data.
          </p>
        </div>
      )}
    </div>
  );
}
