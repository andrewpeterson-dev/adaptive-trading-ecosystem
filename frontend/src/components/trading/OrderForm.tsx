"use client";

import React, { useState, useCallback } from "react";
import { Loader2, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { apiFetch } from "@/lib/api/client";

interface OrderFormProps {
  onOrderPlaced: () => void;
  isPaperMode?: boolean;
}

export function OrderForm({ onOrderPlaced, isPaperMode }: OrderFormProps) {
  const [symbol, setSymbol] = useState("");
  const [direction, setDirection] = useState<"long" | "short">("long");
  const [quantity, setQuantity] = useState("");
  const [price, setPrice] = useState<number | null>(null);
  const [fetchingPrice, setFetchingPrice] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const fetchPrice = useCallback(async (sym: string) => {
    if (!sym || sym.length < 1) {
      setPrice(null);
      return;
    }
    setFetchingPrice(true);
    try {
      const data = await apiFetch<{ price?: number; last_price?: number; close?: number }>(
        `/api/trading/quote?symbol=${sym.toUpperCase()}`
      );
      setPrice(data.price ?? data.last_price ?? data.close ?? null);
    } catch {
      setPrice(null);
    } finally {
      setFetchingPrice(false);
    }
  }, []);

  const handleSymbolBlur = () => {
    if (symbol.trim()) fetchPrice(symbol.trim());
  };

  const estimatedCost =
    price && quantity ? price * parseFloat(quantity || "0") : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const sym = symbol.trim().toUpperCase();
    const qty = parseFloat(quantity);
    if (!sym) { setError("Symbol is required"); return; }
    if (!qty || qty <= 0) { setError("Quantity must be positive"); return; }

    setSubmitting(true);
    try {
      await apiFetch("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol: sym,
          direction,
          quantity: qty,
          strength: 1.0,
          model_name: "manual",
          order_type: "market",
        }),
      });

      setSuccess(`${direction === "long" ? "Buy" : "Sell"} ${qty} ${sym} submitted`);
      setTimeout(() => setSuccess(null), 4000);
      setSymbol("");
      setQuantity("");
      setPrice(null);
      onOrderPlaced();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="rounded-lg border border-border/50 bg-card p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wider">Place Order</h3>
        {isPaperMode && (
          <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25">
            Paper Mode
          </span>
        )}
      </div>
      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Symbol */}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Symbol</label>
          <input
            type="text"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value.toUpperCase())}
            onBlur={handleSymbolBlur}
            placeholder="AAPL"
            autoCapitalize="characters"
            className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
        </div>

        {/* Direction Toggle */}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Direction</label>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setDirection("long")}
              className={`flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${
                direction === "long"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
              }`}
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              Buy
            </button>
            <button
              type="button"
              onClick={() => setDirection("short")}
              className={`flex items-center justify-center gap-1.5 py-2 rounded-md text-sm font-medium transition-colors ${
                direction === "short"
                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                  : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
              }`}
            >
              <ArrowDownRight className="h-3.5 w-3.5" />
              Sell
            </button>
          </div>
        </div>

        {/* Quantity */}
        <div>
          <label className="text-xs text-muted-foreground block mb-1">Quantity</label>
          <input
            type="number"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="10"
            min="0"
            step="1"
            inputMode="decimal"
            className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono focus:outline-none focus:ring-2 focus:ring-ring/40 focus:border-transparent"
          />
        </div>

        {/* Current Price */}
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">Current Price</span>
          <span className="font-mono">
            {fetchingPrice ? (
              <Loader2 className="h-3 w-3 animate-spin inline" />
            ) : price ? (
              `$${price.toFixed(2)}`
            ) : (
              "—"
            )}
          </span>
        </div>

        {/* Estimated Cost */}
        {estimatedCost !== null && estimatedCost > 0 && (
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Estimated Cost</span>
            <span className="font-mono font-medium">
              ${estimatedCost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
          </div>
        )}

        {/* Error/Success */}
        {error && (
          <div className="text-xs text-red-400 bg-red-400/10 rounded px-3 py-2">{error}</div>
        )}
        {success && (
          <div className="text-xs text-emerald-400 bg-emerald-400/10 rounded px-3 py-2">{success}</div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className={`w-full py-2.5 rounded-md text-sm font-semibold transition-colors ${
            direction === "long"
              ? "bg-emerald-500 hover:bg-emerald-400 text-white"
              : "bg-red-500 hover:bg-red-400 text-white"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
          ) : (
            `${direction === "long" ? "Buy" : "Sell"} ${symbol || "..."}`
          )}
        </button>
      </form>
    </div>
  );
}
