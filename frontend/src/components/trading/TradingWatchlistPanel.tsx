"use client";

import { Eye, Plus, Star, X } from "lucide-react";
import { useCallback } from "react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { usePolling } from "@/hooks/usePolling";
import { apiFetch } from "@/lib/api/client";
import { formatCompactNumber, formatCurrency, formatPercent } from "@/lib/trading/format";
import { useTradeStore } from "@/stores/trade-store";
import type { Quote } from "@/types/trading";

async function fetchWatchlistQuotes(symbols: string[]): Promise<Quote[]> {
  if (symbols.length === 0) return [];
  const response = await apiFetch<{ quotes: Quote[] }>(
    `/api/trading/quotes?symbols=${encodeURIComponent(symbols.join(","))}`,
  );
  return response.quotes || [];
}

export function TradingWatchlistPanel() {
  const symbol = useTradeStore((state) => state.symbol);
  const watchlist = useTradeStore((state) => state.watchlist);
  const setSymbol = useTradeStore((state) => state.setSymbol);
  const addToWatchlist = useTradeStore((state) => state.addToWatchlist);
  const removeFromWatchlist = useTradeStore((state) => state.removeFromWatchlist);

  const quoteFetcher = useCallback(() => fetchWatchlistQuotes(watchlist), [watchlist]);
  const { data: quotes, loading } = usePolling<Quote[]>({
    fetcher: quoteFetcher,
    enabled: watchlist.length > 0,
    interval: 30000,
  });

  const quotesBySymbol = new Map((quotes || []).map((quote) => [quote.symbol.toUpperCase(), quote]));

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Watchlist
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">
            Keep a short list beside the chart.
          </p>
        </div>
        <Button onClick={() => addToWatchlist(symbol)} variant="secondary" size="sm">
          <Plus className="h-3.5 w-3.5" />
          Add {symbol}
        </Button>
      </div>

      {watchlist.length === 0 ? (
        <EmptyState
          icon={<Star className="h-5 w-5 text-muted-foreground" />}
          title="No symbols in watchlist"
          description="Pin symbols from the snapshot card or use the add button to keep a compact market board beside the chart."
          className="py-8"
        />
      ) : (
        <div className="mt-4 space-y-2">
          {watchlist.map((item) => {
            const quote = quotesBySymbol.get(item.toUpperCase());
            const active = item.toUpperCase() === symbol.toUpperCase();
            const change = quote?.change_pct ?? null;
            const positive = change != null && change >= 0;

            return (
              <div
                key={item}
                className={`flex items-center gap-3 rounded-3xl border px-4 py-3 transition-colors ${
                  active
                    ? "border-primary/35 bg-primary/10"
                    : "border-border/60 bg-muted/20 hover:border-border hover:bg-muted/35"
                }`}
              >
                <button
                  type="button"
                  onClick={() => setSymbol(item)}
                  className="flex min-w-0 flex-1 items-center gap-3 text-left"
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-sm font-semibold text-foreground">{item}</span>
                      {active && (
                        <span className="rounded-full border border-primary/25 bg-primary/12 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-primary">
                          Active
                        </span>
                      )}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                      <span>{loading && !quote ? "Refreshing..." : formatCurrency(quote?.price)}</span>
                      <span className={positive ? "text-emerald-300" : "text-red-200"}>
                        {change == null ? "—" : formatPercent(change)}
                      </span>
                      <span>Vol {formatCompactNumber(quote?.volume)}</span>
                    </div>
                  </div>

                  <Eye className="h-4 w-4 shrink-0 text-muted-foreground" />
                </button>
                <button
                  type="button"
                  onClick={(event) => {
                    event.stopPropagation();
                    removeFromWatchlist(item);
                  }}
                  className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
                  aria-label={`Remove ${item} from watchlist`}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
