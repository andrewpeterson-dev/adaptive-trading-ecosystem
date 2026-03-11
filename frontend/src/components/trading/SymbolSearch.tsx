"use client";

import { useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { Building2, Clock3, Search, TrendingUp, X } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { formatCompactNumber, formatCurrency, formatPercent } from "@/lib/trading/format";
import { getCatalogSymbol, rankSymbols } from "@/lib/trading/symbol-catalog";
import { cn } from "@/lib/utils";
import { useTradeStore } from "@/stores/trade-store";
import type { Quote, SymbolSearchResult } from "@/types/trading";

const RECENT_KEY = "trade_recent_symbols";
const MAX_RECENT = 8;

function loadRecentSymbols(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(RECENT_KEY);
    return stored ? (JSON.parse(stored) as string[]) : [];
  } catch {
    return [];
  }
}

function storeRecentSymbol(symbol: string): void {
  const recent = loadRecentSymbols().filter((entry) => entry !== symbol);
  recent.unshift(symbol);
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent.slice(0, MAX_RECENT)));
}

export function SymbolSearch() {
  const symbol = useTradeStore((state) => state.symbol);
  const setSymbol = useTradeStore((state) => state.setSymbol);

  const [input, setInput] = useState(symbol);
  const [isOpen, setIsOpen] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const [quotesBySymbol, setQuotesBySymbol] = useState<Record<string, Quote>>({});

  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const deferredInput = useDeferredValue(input.trim());

  useEffect(() => {
    setInput(symbol);
  }, [symbol]);

  useEffect(() => {
    if (!isOpen) return;
    setRecent(loadRecentSymbols());
  }, [isOpen]);

  useEffect(() => {
    function handlePointerDown(event: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, []);

  const rankedResults = useMemo(() => rankSymbols(deferredInput, 8), [deferredInput]);

  useEffect(() => {
    let cancelled = false;

    async function loadResultQuotes(results: SymbolSearchResult[]) {
      if (results.length === 0) {
        if (!cancelled) setQuotesBySymbol({});
        return;
      }

      try {
        const data = await apiFetch<{ quotes: Quote[] }>(
          `/api/trading/quotes?symbols=${results.map((item) => item.symbol).join(",")}`,
        );
        if (cancelled) return;

        const nextMap = (data.quotes || []).reduce<Record<string, Quote>>((acc, quote) => {
          acc[quote.symbol] = quote;
          return acc;
        }, {});
        setQuotesBySymbol(nextMap);
      } catch {
        if (!cancelled) setQuotesBySymbol({});
      }
    }

    void loadResultQuotes(rankedResults);
    return () => {
      cancelled = true;
    };
  }, [rankedResults]);

  const commitSymbol = (nextSymbol: string) => {
    const upper = nextSymbol.trim().toUpperCase();
    if (!upper) return;
    setInput(upper);
    setSymbol(upper);
    storeRecentSymbol(upper);
    setIsOpen(false);
  };

  const clearInput = () => {
    setInput("");
    setQuotesBySymbol({});
    inputRef.current?.focus();
  };

  const showResults = deferredInput.length > 0;
  const recentItems = recent
    .map((entry) => getCatalogSymbol(entry))
    .filter((entry): entry is SymbolSearchResult => Boolean(entry));

  return (
    <div ref={wrapperRef} className="relative">
      <div className="rounded-[24px] border border-border/70 bg-background/80 p-3 shadow-[0_20px_45px_-38px_hsl(var(--shadow-color)/0.9)]">
        <div className="mb-2 flex items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Search Securities
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Ranked by symbol, company, and exchange match.
            </p>
          </div>
          <div className="app-pill shrink-0">
            <span className="font-mono font-semibold text-foreground">{symbol}</span>
          </div>
        </div>

        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onFocus={() => setIsOpen(true)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                commitSymbol(input);
              }
              if (event.key === "Escape") {
                setIsOpen(false);
                inputRef.current?.blur();
              }
            }}
            placeholder="Search by symbol or company"
            className="app-input pl-10 pr-10 font-mono text-sm"
          />
          {input && (
            <button
              type="button"
              onClick={clearInput}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {isOpen && (
        <div className="app-panel absolute left-0 right-0 z-30 mt-3 overflow-hidden p-2">
          {showResults ? (
            rankedResults.length > 0 ? (
              <div className="space-y-1">
                {rankedResults.map((result) => {
                  const quote = quotesBySymbol[result.symbol];
                  const isPositive = (quote?.change ?? 0) >= 0;

                  return (
                    <button
                      key={result.symbol}
                      type="button"
                      onMouseDown={(event) => {
                        event.preventDefault();
                        commitSymbol(result.symbol);
                      }}
                      className="grid w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-3 rounded-[20px] px-3 py-3 text-left transition-colors hover:bg-muted/45"
                    >
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-sm font-semibold text-foreground">
                            {result.symbol}
                          </span>
                          <span className="rounded-full border border-border/70 bg-muted/30 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                            {result.exchange}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-xs text-muted-foreground">{result.name}</p>
                      </div>

                      <div className="text-right">
                        <div className="font-mono text-sm font-semibold text-foreground">
                          {formatCurrency(quote?.price ?? null)}
                        </div>
                        <div
                          className={cn(
                            "mt-1 font-mono text-[11px] font-medium",
                            isPositive ? "text-emerald-300" : "text-red-300",
                          )}
                        >
                          {formatPercent(quote?.change_pct ?? null)}
                        </div>
                        <div className="mt-1 text-[11px] text-muted-foreground">
                          Vol {formatCompactNumber(quote?.volume ?? null)}
                        </div>
                      </div>
                    </button>
                  );
                })}
              </div>
            ) : (
              <div className="rounded-[18px] border border-dashed border-border/70 px-4 py-5 text-center">
                <p className="text-sm font-medium text-foreground">
                  No ranked match for “{deferredInput.toUpperCase()}”
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Press Enter to open the symbol directly if you know the ticker.
                </p>
              </div>
            )
          ) : recentItems.length > 0 ? (
            <div className="space-y-2">
              <div className="flex items-center gap-2 px-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                <Clock3 className="h-3.5 w-3.5" />
                Recent Symbols
              </div>
              <div className="flex flex-wrap gap-2">
                {recentItems.map((item) => (
                  <button
                    key={item.symbol}
                    type="button"
                    onMouseDown={(event) => {
                      event.preventDefault();
                      commitSymbol(item.symbol);
                    }}
                    className="inline-flex items-center gap-2 rounded-full border border-border/70 bg-muted/35 px-3 py-2 text-xs transition-colors hover:bg-muted/55"
                  >
                    <TrendingUp className="h-3.5 w-3.5 text-muted-foreground" />
                    <span className="font-mono font-semibold text-foreground">{item.symbol}</span>
                    <span className="hidden text-muted-foreground sm:inline">{item.name}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="rounded-[18px] border border-dashed border-border/70 px-4 py-5 text-center">
              <Building2 className="mx-auto h-5 w-5 text-muted-foreground" />
              <p className="mt-2 text-sm font-medium text-foreground">
                Start with a ticker, company name, or ETF.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
