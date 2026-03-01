"use client";

import React from "react";
import { TrendingUp, TrendingDown, Minus } from "lucide-react";

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
    ? "text-emerald-400"
    : "text-red-400";
  const changeBg = isFlat
    ? "bg-muted"
    : isUp
    ? "bg-emerald-400/10"
    : "bg-red-400/10";

  const rangeWidth =
    quote.high && quote.low && quote.high !== quote.low
      ? ((quote.price - quote.low) / (quote.high - quote.low)) * 100
      : 50;

  return (
    <div className="rounded-lg border border-border/50 bg-card p-4 space-y-3 group">
      <div className="flex items-center justify-between">
        <div>
          <div className="font-mono font-semibold text-sm">{quote.symbol}</div>
          {quote.name && (
            <div className="text-xs text-muted-foreground truncate max-w-[140px]">
              {quote.name}
            </div>
          )}
        </div>
        {onRemove && (
          <button
            onClick={() => onRemove(quote.symbol)}
            className="text-[10px] text-muted-foreground/50 hover:text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity"
          >
            Remove
          </button>
        )}
      </div>

      <div className="flex items-end justify-between">
        <span className="text-xl font-mono tabular-nums font-bold">
          ${quote.price.toFixed(2)}
        </span>
        <div className={`flex items-center gap-1 text-xs font-medium tabular-nums px-1.5 py-0.5 rounded ${changeBg} ${changeColor}`}>
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

      {/* High/Low range bar */}
      {quote.high != null && quote.low != null && (
        <div>
          <div className="flex justify-between text-[10px] tabular-nums text-muted-foreground mb-0.5">
            <span>${quote.low.toFixed(2)}</span>
            <span>${quote.high.toFixed(2)}</span>
          </div>
          <div className="h-1.5 rounded-full bg-muted overflow-hidden relative">
            <div
              className="h-full rounded-full bg-primary/60"
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
