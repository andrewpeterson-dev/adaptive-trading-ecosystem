"use client";

import React from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { QuoteData } from "./QuoteCard";

interface WatchlistRowProps {
  quote: QuoteData;
  onRemove?: (symbol: string) => void;
  onTrade?: (symbol: string) => void;
}

export function WatchlistRow({ quote, onRemove, onTrade }: WatchlistRowProps) {
  const isUp = quote.change >= 0;
  const changeColor = isUp ? "text-emerald-400" : "text-red-400";

  return (
    <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors group">
      <td className="py-2.5 px-4">
        <div className="flex items-center gap-2">
          <span className="font-mono font-medium text-sm">{quote.symbol}</span>
          {quote.name && (
            <span className="text-xs text-muted-foreground hidden sm:inline truncate max-w-[120px]">
              {quote.name}
            </span>
          )}
        </div>
      </td>
      <td className="py-2.5 px-4 font-mono text-sm font-medium">
        ${quote.price.toFixed(2)}
      </td>
      <td className={`py-2.5 px-4 font-mono text-sm ${changeColor}`}>
        <div className="flex items-center gap-1">
          {isUp ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {isUp ? "+" : ""}
          {quote.change.toFixed(2)}
        </div>
      </td>
      <td className={`py-2.5 px-4 font-mono text-sm ${changeColor}`}>
        {isUp ? "+" : ""}
        {quote.change_pct.toFixed(2)}%
      </td>
      <td className="py-2.5 px-4 font-mono text-xs text-muted-foreground">
        {quote.volume != null
          ? quote.volume >= 1_000_000
            ? `${(quote.volume / 1_000_000).toFixed(1)}M`
            : quote.volume >= 1_000
            ? `${(quote.volume / 1_000).toFixed(1)}K`
            : quote.volume.toLocaleString()
          : "—"}
      </td>
      <td className="py-2.5 px-4">
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          {onTrade && (
            <button
              onClick={() => onTrade(quote.symbol)}
              className="text-xs px-2 py-1 rounded bg-primary/10 text-primary hover:bg-primary/20 transition-colors"
            >
              Trade
            </button>
          )}
          {onRemove && (
            <button
              onClick={() => onRemove(quote.symbol)}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Remove
            </button>
          )}
        </div>
      </td>
    </tr>
  );
}
