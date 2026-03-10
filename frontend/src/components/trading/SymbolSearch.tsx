"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { Search } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";

const RECENT_KEY = "trade_recent_symbols";
const MAX_RECENT = 8;

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
  const [input, setInput] = useState(symbol);
  const [focused, setFocused] = useState(false);
  const [recent, setRecent] = useState<string[]>([]);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

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

    // Debounce: only commit after 600ms of no typing
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
  };

  const handleBlur = () => {
    // Short delay to allow chip clicks to register
    setTimeout(() => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
      const trimmed = input.trim().toUpperCase();
      if (trimmed && trimmed !== symbol) {
        commitSymbol(trimmed);
      }
    }, 150);
  };

  const handleChipClick = (sym: string) => {
    commitSymbol(sym);
  };

  return (
    <div ref={wrapperRef} className="relative">
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted-foreground" />
        <input
          type="text"
          value={input}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={handleBlur}
          placeholder="Symbol"
          className="w-full pl-9 pr-3 py-2 rounded-md border border-border/50 bg-card text-sm font-mono text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-primary/50"
        />
      </div>
      {focused && recent.length > 0 && (
        <div className="absolute z-20 mt-1.5 w-full rounded-md border border-border/50 bg-card p-2 shadow-lg">
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Recent
          </div>
          <div className="flex flex-wrap gap-1.5">
            {recent.map((sym) => (
              <button
                key={sym}
                type="button"
                onMouseDown={(e) => {
                  e.preventDefault();
                  handleChipClick(sym);
                }}
                className="px-2.5 py-1 rounded-md text-xs font-mono font-medium bg-muted text-muted-foreground hover:text-foreground hover:bg-muted/80 transition-colors"
              >
                {sym}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
