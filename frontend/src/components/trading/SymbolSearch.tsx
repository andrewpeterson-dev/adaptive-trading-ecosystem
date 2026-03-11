"use client";

import React, { useState, useRef, useEffect, useCallback, useMemo } from "react";
import { Search, X, Clock, TrendingUp } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import type { SymbolSearchResult } from "@/types/trading";

const RECENT_KEY = "trade_recent_symbols";
const MAX_RECENT = 8;

// Static symbol map for client-side autocomplete (replace with API later)
const SYMBOL_MAP: SymbolSearchResult[] = [
  { symbol: "AAPL", name: "Apple Inc.", type: "stock" },
  { symbol: "MSFT", name: "Microsoft Corporation", type: "stock" },
  { symbol: "GOOGL", name: "Alphabet Inc.", type: "stock" },
  { symbol: "AMZN", name: "Amazon.com Inc.", type: "stock" },
  { symbol: "NVDA", name: "NVIDIA Corporation", type: "stock" },
  { symbol: "META", name: "Meta Platforms Inc.", type: "stock" },
  { symbol: "TSLA", name: "Tesla Inc.", type: "stock" },
  { symbol: "BRK.B", name: "Berkshire Hathaway Inc.", type: "stock" },
  { symbol: "JPM", name: "JPMorgan Chase & Co.", type: "stock" },
  { symbol: "V", name: "Visa Inc.", type: "stock" },
  { symbol: "JNJ", name: "Johnson & Johnson", type: "stock" },
  { symbol: "WMT", name: "Walmart Inc.", type: "stock" },
  { symbol: "MA", name: "Mastercard Inc.", type: "stock" },
  { symbol: "PG", name: "Procter & Gamble Co.", type: "stock" },
  { symbol: "UNH", name: "UnitedHealth Group Inc.", type: "stock" },
  { symbol: "HD", name: "The Home Depot Inc.", type: "stock" },
  { symbol: "DIS", name: "The Walt Disney Company", type: "stock" },
  { symbol: "BAC", name: "Bank of America Corp.", type: "stock" },
  { symbol: "ADBE", name: "Adobe Inc.", type: "stock" },
  { symbol: "CRM", name: "Salesforce Inc.", type: "stock" },
  { symbol: "NFLX", name: "Netflix Inc.", type: "stock" },
  { symbol: "AMD", name: "Advanced Micro Devices", type: "stock" },
  { symbol: "INTC", name: "Intel Corporation", type: "stock" },
  { symbol: "CSCO", name: "Cisco Systems Inc.", type: "stock" },
  { symbol: "ORCL", name: "Oracle Corporation", type: "stock" },
  { symbol: "PFE", name: "Pfizer Inc.", type: "stock" },
  { symbol: "ABT", name: "Abbott Laboratories", type: "stock" },
  { symbol: "KO", name: "The Coca-Cola Company", type: "stock" },
  { symbol: "PEP", name: "PepsiCo Inc.", type: "stock" },
  { symbol: "TMO", name: "Thermo Fisher Scientific", type: "stock" },
  { symbol: "COST", name: "Costco Wholesale Corp.", type: "stock" },
  { symbol: "AVGO", name: "Broadcom Inc.", type: "stock" },
  { symbol: "MRK", name: "Merck & Co. Inc.", type: "stock" },
  { symbol: "ABBV", name: "AbbVie Inc.", type: "stock" },
  { symbol: "ACN", name: "Accenture plc", type: "stock" },
  { symbol: "LLY", name: "Eli Lilly and Company", type: "stock" },
  { symbol: "QCOM", name: "Qualcomm Inc.", type: "stock" },
  { symbol: "NOW", name: "ServiceNow Inc.", type: "stock" },
  { symbol: "COIN", name: "Coinbase Global Inc.", type: "stock" },
  { symbol: "PLTR", name: "Palantir Technologies", type: "stock" },
  { symbol: "SOFI", name: "SoFi Technologies Inc.", type: "stock" },
  { symbol: "RIVN", name: "Rivian Automotive Inc.", type: "stock" },
  { symbol: "SPY", name: "SPDR S&P 500 ETF Trust", type: "etf" },
  { symbol: "QQQ", name: "Invesco QQQ Trust", type: "etf" },
  { symbol: "IWM", name: "iShares Russell 2000 ETF", type: "etf" },
  { symbol: "DIA", name: "SPDR Dow Jones Industrial", type: "etf" },
  { symbol: "VTI", name: "Vanguard Total Stock Market", type: "etf" },
  { symbol: "ARKK", name: "ARK Innovation ETF", type: "etf" },
  { symbol: "XLF", name: "Financial Select Sector SPDR", type: "etf" },
  { symbol: "XLE", name: "Energy Select Sector SPDR", type: "etf" },
  { symbol: "GLD", name: "SPDR Gold Shares", type: "etf" },
  { symbol: "TLT", name: "iShares 20+ Year Treasury", type: "etf" },
];

function getRecentSymbols(): string[] {
  if (typeof window === "undefined") return [];
  try {
    const stored = localStorage.getItem(RECENT_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

function addRecentSymbol(symbol: string): void {
  const recent = getRecentSymbols().filter((s) => s !== symbol);
  recent.unshift(symbol);
  if (recent.length > MAX_RECENT) recent.length = MAX_RECENT;
  localStorage.setItem(RECENT_KEY, JSON.stringify(recent));
}

export function SymbolSearch() {
  const symbol = useTradeStore((s) => s.symbol);
  const setSymbol = useTradeStore((s) => s.setSymbol);
  const quote = useTradeStore((s) => s.quote);

  const [input, setInput] = useState(symbol);
  const [focused, setFocused] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync input when store symbol changes externally
  useEffect(() => {
    setInput(symbol);
  }, [symbol]);

  // Load recent symbols on focus
  useEffect(() => {
    if (focused) {
      setRecent(getRecentSymbols());
    }
  }, [focused]);

  // Close dropdown on outside click
  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setFocused(false);
      }
    }
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, []);

  // Autocomplete results
  const searchResults = useMemo(() => {
    const q = input.trim().toUpperCase();
    if (!q || q.length < 1) return [];
    return SYMBOL_MAP.filter(
      (s) =>
        s.symbol.startsWith(q) ||
        s.name.toUpperCase().includes(q)
    ).slice(0, 8);
  }, [input]);

  const commitSymbol = useCallback(
    (sym: string) => {
      const upper = sym.trim().toUpperCase();
      if (!upper) return;
      setInput(upper);
      setSymbol(upper);
      addRecentSymbol(upper);
      setFocused(false);
    },
    [setSymbol]
  );

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value.toUpperCase();
    setInput(val);

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      const trimmed = val.trim();
      if (trimmed && trimmed !== symbol) {
        commitSymbol(trimmed);
      }
    }, 600);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      if (debounceRef.current) clearTimeout(debounceRef.current);
      commitSymbol(input);
    }
    if (e.key === "Escape") {
      setFocused(false);
      inputRef.current?.blur();
    }
  };

  const handleBlur = () => {
    setTimeout(() => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const trimmed = input.trim().toUpperCase();
      if (trimmed && trimmed !== symbol) {
        commitSymbol(trimmed);
      }
    }, 200);
  };

  const handleSelectResult = (sym: string) => {
    commitSymbol(sym);
  };

  const clearInput = () => {
    setInput("");
    inputRef.current?.focus();
  };

  const showDropdown = focused && (searchResults.length > 0 || recent.length > 0);
  const showResults = input.trim().length > 0 && input.trim().toUpperCase() !== symbol;

  // Get company name from static map
  const companyName = useMemo(() => {
    const match = SYMBOL_MAP.find((s) => s.symbol === symbol);
    return quote?.name || match?.name || null;
  }, [symbol, quote?.name]);

  return (
    <div ref={wrapperRef} className="relative">
      {/* Input row with current symbol info */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={handleChange}
            onKeyDown={handleKeyDown}
            onFocus={() => setFocused(true)}
            onBlur={handleBlur}
            placeholder="Search symbol or company..."
            className="w-full pl-9 pr-8 py-2 rounded-md border border-border/50 bg-card text-sm font-mono text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 focus:ring-primary/50"
          />
          {input && (
            <button
              type="button"
              onMouseDown={(e) => {
                e.preventDefault();
                clearInput();
              }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        {/* Current symbol badge */}
        {companyName && !focused && (
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-muted-foreground shrink-0">
            <span className="font-mono font-bold text-foreground">{symbol}</span>
            <span className="truncate max-w-[180px]">{companyName}</span>
          </div>
        )}
      </div>

      {/* Dropdown */}
      {showDropdown && (
        <div className="absolute z-30 mt-1.5 w-full rounded-lg border border-border/50 bg-card shadow-xl overflow-hidden">
          {/* Autocomplete results */}
          {showResults && searchResults.length > 0 && (
            <div className="p-2">
              <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5 px-1">
                Results
              </div>
              {searchResults.map((result) => (
                <button
                  key={result.symbol}
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    handleSelectResult(result.symbol);
                  }}
                  className="flex items-center gap-3 w-full px-2.5 py-2 rounded-md text-left hover:bg-muted/50 transition-colors"
                >
                  <span className="font-mono font-bold text-sm text-foreground w-16 shrink-0">
                    {result.symbol}
                  </span>
                  <span className="text-xs text-muted-foreground truncate flex-1">
                    {result.name}
                  </span>
                  <span className="text-[10px] font-medium text-muted-foreground/60 uppercase">
                    {result.type}
                  </span>
                </button>
              ))}
            </div>
          )}

          {/* Recent symbols */}
          {(!showResults || searchResults.length === 0) && recent.length > 0 && (
            <div className="p-2">
              <div className="flex items-center gap-1.5 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5 px-1">
                <Clock className="h-3 w-3" />
                Recent
              </div>
              <div className="flex flex-wrap gap-1.5 px-1">
                {recent.map((sym) => {
                  const info = SYMBOL_MAP.find((s) => s.symbol === sym);
                  return (
                    <button
                      key={sym}
                      type="button"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        handleSelectResult(sym);
                      }}
                      className="group flex items-center gap-1.5 px-2.5 py-1.5 rounded-md text-xs font-mono bg-muted hover:bg-muted/80 transition-colors"
                    >
                      <TrendingUp className="h-3 w-3 text-muted-foreground/50 group-hover:text-muted-foreground" />
                      <span className="font-bold text-foreground">{sym}</span>
                      {info && (
                        <span className="text-muted-foreground/60 hidden sm:inline">
                          {info.name.length > 15 ? info.name.slice(0, 15) + "…" : info.name}
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>
          )}

          {/* No results */}
          {showResults && searchResults.length === 0 && (
            <div className="p-3 text-xs text-muted-foreground text-center">
              No matches — press Enter to search &quot;{input.trim().toUpperCase()}&quot;
            </div>
          )}
        </div>
      )}
    </div>
  );
}
