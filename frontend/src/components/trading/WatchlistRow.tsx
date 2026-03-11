"use client";

import React from "react";
import { TrendingUp, TrendingDown } from "lucide-react";
import type { QuoteData } from "./QuoteCard";
import { Button } from "@/components/ui/button";

interface WatchlistRowProps {
  quote: QuoteData;
  onRemove?: (symbol: string) => void;
  onTrade?: (symbol: string) => void;
}

export function WatchlistRow({ quote, onRemove, onTrade }: WatchlistRowProps) {
  const isUp = quote.change >= 0;
  const changeColor = isUp ? "text-emerald-300" : "text-red-300";

  return (
    <tr>
      <td>
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-medium">{quote.symbol}</span>
          {quote.name && (
            <span className="hidden max-w-[140px] truncate text-xs text-muted-foreground sm:inline">
              {quote.name}
            </span>
          )}
        </div>
      </td>
      <td className="font-mono text-sm font-medium tabular-nums">
        ${quote.price.toFixed(2)}
      </td>
      <td className={`font-mono text-sm tabular-nums ${changeColor}`}>
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
      <td className={`font-mono text-sm tabular-nums ${changeColor}`}>
        {isUp ? "+" : ""}
        {quote.change_pct.toFixed(2)}%
      </td>
      <td className="font-mono text-xs tabular-nums text-muted-foreground">
        {quote.volume != null
          ? quote.volume >= 1_000_000
            ? `${(quote.volume / 1_000_000).toFixed(1)}M`
            : quote.volume >= 1_000
              ? `${(quote.volume / 1_000).toFixed(1)}K`
              : quote.volume.toLocaleString()
          : "—"}
      </td>
      <td>
        <div className="flex items-center justify-end gap-2">
          {onTrade && (
            <Button
              onClick={() => onTrade(quote.symbol)}
              variant="secondary"
              size="sm"
              className="h-8 px-3 text-[10px] uppercase tracking-[0.16em]"
            >
              Trade
            </Button>
          )}
          {onRemove && (
            <Button
              onClick={() => onRemove(quote.symbol)}
              variant="ghost"
              size="sm"
              className="h-8 px-2.5 text-[10px] uppercase tracking-[0.16em]"
            >
              Remove
            </Button>
          )}
        </div>
      </td>
    </tr>
  );
}
