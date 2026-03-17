"use client";

import React, { useState, useCallback, useEffect } from "react";
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
import { PageHeader } from "@/components/layout/PageHeader";
import { SubNav } from "@/components/layout/SubNav";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/empty-state";
import { Badge } from "@/components/ui/badge";

const STORAGE_KEY = "watchlist_symbols";

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

function loadSymbols(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as string[];
  } catch {
    // no-op
  }
  return [];
}

export default function WatchlistPage() {
  const [symbols, setSymbolsRaw] = useState<string[]>([]);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [addInput, setAddInput] = useState("");
  const [regime, setRegime] = useState<string | null>(null);

  // Hydrate watchlist from localStorage after mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        setSymbolsRaw(JSON.parse(stored));
      } catch {
        // ignore corrupt data
      }
    }
  }, []);

  const setSymbols = useCallback((next: string[] | ((prev: string[]) => string[])) => {
    setSymbolsRaw((prev) => {
      const value = typeof next === "function" ? next(prev) : next;
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
      } catch {
        // no-op
      }
      return value;
    });
  }, []);

  const quoteFetcher = useCallback(() => fetchQuotes(symbols), [symbols]);
  const { data: quotes, loading, refresh } = usePolling<QuoteData[]>({
    fetcher: quoteFetcher,
    interval: 60000,
    enabled: symbols.length > 0,
  });

  useEffect(() => {
    fetchRegime().then(setRegime);
  }, []);

  const addSymbol = () => {
    const symbol = addInput.trim().toUpperCase();
    if (symbol && !symbols.includes(symbol)) {
      setSymbols((prev) => [...prev, symbol]);
      setAddInput("");
    }
  };

  const removeSymbol = (symbol: string) => {
    setSymbols((prev) => prev.filter((item) => item !== symbol));
  };

  const handleAddKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "Enter") addSymbol();
  };

  const regimeLabel =
    regime?.replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase()) || null;

  return (
    <div className="app-page">
      <SubNav items={[
        { href: "/trade", label: "Workspace" },
        { href: "/watchlist", label: "Watchlist" },
      ]} />

      <PageHeader
        eyebrow="Market Pulse"
        title="Watchlist"
        description="Track the tickers that matter, switch between a dense list and high-signal cards, and keep regime context visible while you scan."
        badge={
          regimeLabel ? (
            <Badge variant="info">
              <Activity className="h-3.5 w-3.5" />
              {regimeLabel}
            </Badge>
          ) : undefined
        }
        meta={
          <Badge variant="neutral" className="tracking-normal">
            <span className="font-mono">{symbols.length}</span>
            symbol{symbols.length !== 1 ? "s" : ""}
          </Badge>
        }
        actions={
          <>
            <Button
              onClick={() => setView(view === "grid" ? "list" : "grid")}
              variant="secondary"
              size="sm"
            >
              {view === "grid" ? (
                <List className="h-3.5 w-3.5" />
              ) : (
                <LayoutGrid className="h-3.5 w-3.5" />
              )}
              {view === "grid" ? "List" : "Grid"}
            </Button>
            <Button onClick={refresh} variant="secondary" size="sm">
              <RefreshCw className="h-3.5 w-3.5" />
              Refresh
            </Button>
          </>
        }
      />

      <div className="app-panel p-4 sm:p-5">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <Input
            type="text"
            value={addInput}
            onChange={(event) => setAddInput(event.target.value.toUpperCase())}
            onKeyDown={handleAddKeyDown}
            placeholder="Add ticker"
            className="max-w-xs font-mono"
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              onClick={addSymbol}
              disabled={!addInput.trim()}
              variant="primary"
              size="sm"
            >
              <Plus className="h-3.5 w-3.5" />
              Add Symbol
            </Button>
            {symbols.length > 0 && (
              <Button onClick={() => setSymbols([])} variant="ghost" size="sm">
                Clear all
              </Button>
            )}
          </div>
        </div>
      </div>

      {loading && !quotes && (
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
        </div>
      )}

      {quotes && view === "grid" && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {quotes.map((quote) => (
            <QuoteCard key={quote.symbol} quote={quote} onRemove={removeSymbol} />
          ))}
        </div>
      )}

      {quotes && view === "list" && (
        <div className="app-table-shell overflow-x-auto">
          <table className="app-table">
            <thead>
              <tr>
                <th>Symbol</th>
                <th>Price</th>
                <th>Change</th>
                <th>% Change</th>
                <th>Volume</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {quotes.map((quote) => (
                <WatchlistRow
                  key={quote.symbol}
                  quote={quote}
                  onRemove={removeSymbol}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {!loading && symbols.length > 0 && quotes && quotes.length === 0 && (
        <EmptyState
          icon={<Activity className="h-5 w-5 text-amber-300" />}
          title="No quote data available"
          description={`Could not fetch live prices for ${symbols.join(", ")}. The market may be closed or the data API is unavailable.`}
          action={
            <Button onClick={refresh} variant="secondary" size="sm">
              <RefreshCw className="h-3.5 w-3.5" />
              Retry
            </Button>
          }
        />
      )}

      {!loading && symbols.length === 0 && (
        <EmptyState
          icon={<Activity className="h-5 w-5 text-muted-foreground" />}
          title="No symbols tracked"
          description="Add a ticker above to start monitoring live pricing, day ranges, and volume from the same workspace."
        />
      )}
    </div>
  );
}
