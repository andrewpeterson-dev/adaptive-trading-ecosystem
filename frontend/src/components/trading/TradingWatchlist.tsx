"use client";

import { useEffect, useState } from "react";
import { Eye, Star, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { formatCompactNumber, formatCurrency, formatPercent } from "@/lib/trading/format";
import { useTradeStore } from "@/stores/trade-store";
import type { Quote } from "@/types/trading";

export function TradingWatchlist() {
  const symbol = useTradeStore((state) => state.symbol);
  const watchlist = useTradeStore((state) => state.watchlist);
  const setSymbol = useTradeStore((state) => state.setSymbol);
  const removeFromWatchlist = useTradeStore((state) => state.removeFromWatchlist);

  const [quotes, setQuotes] = useState<Record<string, Quote>>({});

  useEffect(() => {
    let cancelled = false;

    async function loadQuotes() {
      if (watchlist.length === 0) {
        setQuotes({});
        return;
      }

      try {
        const data = await apiFetch<{ quotes: Quote[] }>(
          `/api/trading/quotes?symbols=${watchlist.map((s) => encodeURIComponent(s)).join(",")}`,
        );
        if (cancelled) return;
        setQuotes(
          (data.quotes || []).reduce<Record<string, Quote>>((acc, quote) => {
            acc[quote.symbol] = quote;
            return acc;
          }, {}),
        );
      } catch {
        if (!cancelled) setQuotes({});
      }
    }

    void loadQuotes();
    return () => {
      cancelled = true;
    };
  }, [watchlist]);

  if (watchlist.length === 0) {
    return (
      <div className="app-panel p-4">
        <EmptyState
          icon={<Star className="h-5 w-5 text-muted-foreground" />}
          title="Watchlist empty"
          description="Add a symbol from the snapshot card to keep the left drawer populated with your active names."
        />
      </div>
    );
  }

  return (
    <div className="app-panel p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Watchlist
          </p>
          <p className="mt-1 text-xs text-muted-foreground">
            Fast access to the symbols you are actively monitoring.
          </p>
        </div>
      </div>

      <div className="space-y-2">
        {watchlist.map((item) => {
          const quote = quotes[item];
          const isActive = item === symbol;
          const isPositive = (quote?.change ?? 0) >= 0;

          return (
            <div
              key={item}
              className={`rounded-[18px] border px-3 py-3 transition-colors ${
                isActive
                  ? "border-primary/35 bg-primary/8"
                  : "border-border/70 bg-background/70"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <button
                  type="button"
                  onClick={() => setSymbol(item)}
                  className="min-w-0 text-left"
                >
                  <div className="font-mono text-sm font-semibold text-foreground">{item}</div>
                  <div className="mt-1 text-xs text-muted-foreground">
                    {formatCurrency(quote?.price ?? null)} · {formatPercent(quote?.change_pct ?? null)}
                  </div>
                </button>

                <div className="flex items-center gap-1">
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2.5"
                    onClick={() => setSymbol(item)}
                  >
                    <Eye className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    className="h-8 px-2.5"
                    onClick={() => removeFromWatchlist(item)}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </div>

              <div className="mt-3 flex items-center justify-between text-[11px] text-muted-foreground">
                <span>Volume {formatCompactNumber(quote?.volume ?? null)}</span>
                <span className={isPositive ? "text-emerald-300" : "text-red-300"}>
                  {quote?.change != null ? quote.change.toFixed(2) : "—"}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
