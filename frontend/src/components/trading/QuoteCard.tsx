"use client";

import React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface QuoteData {
  symbol: string;
  name?: string;
  price: number;
  change: number;
  change_pct: number;
  volume?: number;
  high?: number;
  low?: number;
}

interface QuoteCardProps {
  quote: QuoteData;
  onRemove?: (symbol: string) => void;
}

export function QuoteCard({ quote, onRemove }: QuoteCardProps) {
  const isUp = quote.change >= 0;
  const isFlat = quote.change === 0;
  const changeColor = isFlat
    ? "text-muted-foreground"
    : isUp
      ? "text-emerald-300"
      : "text-red-300";

  const rangeWidth =
    quote.high && quote.low && quote.high !== quote.low
      ? ((quote.price - quote.low) / (quote.high - quote.low)) * 100
      : 50;

  return (
    <div className="app-card group space-y-4 p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="font-mono text-base font-semibold">{quote.symbol}</div>
          {quote.name && (
            <div className="truncate text-xs text-muted-foreground">{quote.name}</div>
          )}
        </div>
        {onRemove && (
          <Button
            onClick={() => onRemove(quote.symbol)}
            variant="ghost"
            size="sm"
            className="h-8 px-2.5 text-[10px] uppercase tracking-[0.16em] opacity-0 group-hover:opacity-100"
          >
            Remove
          </Button>
        )}
      </div>

      <div className="flex items-end justify-between gap-3">
        <span className="text-[1.65rem] font-mono font-semibold tracking-tight">
          ${quote.price.toFixed(2)}
        </span>
        <div
          className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-semibold ${changeColor} ${
            isFlat
              ? "border-border/75 bg-muted/50"
              : isUp
                ? "border-emerald-400/20 bg-emerald-400/10"
                : "border-red-400/20 bg-red-400/10"
          }`}
        >
          {isFlat ? (
            <Minus className="h-3 w-3" />
          ) : isUp ? (
            <TrendingUp className="h-3 w-3" />
          ) : (
            <TrendingDown className="h-3 w-3" />
          )}
          {isUp ? "+" : ""}
          {quote.change.toFixed(2)} ({isUp ? "+" : ""}
          {quote.change_pct.toFixed(2)}%)
        </div>
      </div>

      {quote.high != null && quote.low != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-muted-foreground">
            <span>${quote.low.toFixed(2)}</span>
            <span>${quote.high.toFixed(2)}</span>
          </div>
          <div className="app-progress-track">
            <div
              className="app-progress-bar bg-primary"
              style={{ width: `${Math.min(100, Math.max(0, rangeWidth))}%` }}
            />
          </div>
        </div>
      )}

      {quote.volume != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Volume</span>
          <span className="font-mono tabular-nums">
            {quote.volume >= 1_000_000
              ? `${(quote.volume / 1_000_000).toFixed(1)}M`
              : quote.volume >= 1_000
                ? `${(quote.volume / 1_000).toFixed(1)}K`
                : quote.volume.toLocaleString()}
          </span>
        </div>
      )}
    </div>
  );
}
