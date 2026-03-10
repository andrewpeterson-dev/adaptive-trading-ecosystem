"use client";

import React, { useState, useCallback, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import { apiFetch } from "@/lib/api/client";
import { OrderPreview } from "./OrderPreview";

type Direction = "buy" | "sell";
type OrderType = "market" | "limit" | "stop" | "stop_limit";

const ORDER_TYPES: { value: OrderType; label: string }[] = [
  { value: "market", label: "Market" },
  { value: "limit", label: "Limit" },
  { value: "stop", label: "Stop" },
  { value: "stop_limit", label: "Stop-Limit" },
];

interface StockOrderTicketProps {
  onOrderPlaced: () => void;
  isPaperMode?: boolean;
}

export function StockOrderTicket({ onOrderPlaced, isPaperMode }: StockOrderTicketProps) {
  const { symbol, quote } = useTradeStore();

  const [direction, setDirection] = useState<Direction>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState(0);
  const [limitPrice, setLimitPrice] = useState<string>("");
  const [stopPrice, setStopPrice] = useState<string>("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Reset fields when symbol changes
  useEffect(() => {
    setQuantity(0);
    setLimitPrice("");
    setStopPrice("");
    setError(null);
    setSuccess(null);
  }, [symbol]);

  const currentPrice = quote?.price ?? quote?.last ?? null;
  const bid = quote?.bid;
  const ask = quote?.ask;
  const last = quote?.last ?? quote?.price;

  // Effective price for estimation
  const effectivePrice = (() => {
    if (orderType === "limit" || orderType === "stop_limit") {
      const lp = parseFloat(limitPrice);
      return !isNaN(lp) && lp > 0 ? lp : currentPrice;
    }
    if (orderType === "stop") {
      const sp = parseFloat(stopPrice);
      return !isNaN(sp) && sp > 0 ? sp : currentPrice;
    }
    return currentPrice;
  })();

  const validate = useCallback((): string | null => {
    if (!symbol) return "Enter a symbol";
    if (quantity <= 0) return "Enter quantity";
    if ((orderType === "limit" || orderType === "stop_limit") && (!limitPrice || parseFloat(limitPrice) <= 0)) {
      return "Enter limit price";
    }
    if ((orderType === "stop" || orderType === "stop_limit") && (!stopPrice || parseFloat(stopPrice) <= 0)) {
      return "Enter stop price";
    }
    return null;
  }, [symbol, quantity, orderType, limitPrice, stopPrice]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    try {
      await apiFetch("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol: symbol.toUpperCase(),
          direction: direction === "buy" ? "long" : "short",
          quantity,
          strength: 1.0,
          model_name: "manual",
          order_type: orderType,
          limit_price: (orderType === "limit" || orderType === "stop_limit") ? parseFloat(limitPrice) : null,
          stop_price: (orderType === "stop" || orderType === "stop_limit") ? parseFloat(stopPrice) : null,
          user_confirmed: true,
        }),
      });

      setSuccess(
        `${direction === "buy" ? "Buy" : "Sell"} ${quantity} ${symbol.toUpperCase()} submitted`
      );
      setQuantity(0);
      setLimitPrice("");
      setStopPrice("");
      onOrderPlaced();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  };

  const decrementQty = () => setQuantity((q) => Math.max(0, q - 1));
  const incrementQty = () => setQuantity((q) => q + 1);

  const submitLabel = quantity > 0 && symbol
    ? `${direction === "buy" ? "Buy" : "Sell"} ${quantity} ${symbol.toUpperCase()}`
    : direction === "buy"
      ? "Buy"
      : "Sell";

  return (
    <div className="rounded-xl border border-border/50 bg-card p-5">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          Order Ticket
        </div>
        {isPaperMode && (
          <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-amber-500/15 text-amber-400 border border-amber-500/25">
            Paper
          </span>
        )}
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Buy / Sell toggle */}
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => setDirection("buy")}
            className={`py-2 rounded-md text-sm font-semibold transition-colors ${
              direction === "buy"
                ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
            }`}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => setDirection("sell")}
            className={`py-2 rounded-md text-sm font-semibold transition-colors ${
              direction === "sell"
                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
            }`}
          >
            Sell
          </button>
        </div>

        {/* Order type selector */}
        <div>
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Order Type
          </div>
          <div className="flex gap-1">
            {ORDER_TYPES.map((ot) => (
              <button
                key={ot.value}
                type="button"
                onClick={() => setOrderType(ot.value)}
                className={`flex-1 px-2 py-1.5 rounded-md text-xs font-medium transition-colors ${
                  orderType === ot.value
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {ot.label}
              </button>
            ))}
          </div>
        </div>

        {/* Conditional price fields */}
        {(orderType === "limit" || orderType === "stop_limit") && (
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
              Limit Price
            </label>
            <input
              type="number"
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              placeholder="0.00"
              min="0"
              step="0.01"
              className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
          </div>
        )}
        {(orderType === "stop" || orderType === "stop_limit") && (
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
              Stop Price
            </label>
            <input
              type="number"
              value={stopPrice}
              onChange={(e) => setStopPrice(e.target.value)}
              placeholder="0.00"
              min="0"
              step="0.01"
              className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
          </div>
        )}

        {/* Quantity */}
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
            Quantity
          </label>
          <div className="flex items-center gap-0">
            <button
              type="button"
              onClick={decrementQty}
              className="px-3 py-2 rounded-l-md bg-muted border border-border text-sm font-mono font-bold hover:bg-muted/80 transition-colors"
            >
              -
            </button>
            <input
              type="number"
              value={quantity}
              onChange={(e) => setQuantity(Math.max(0, parseInt(e.target.value) || 0))}
              min="0"
              step="1"
              className="flex-1 px-3 py-2 bg-muted border-y border-border text-sm font-mono tabular-nums text-center focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            <button
              type="button"
              onClick={incrementQty}
              className="px-3 py-2 rounded-r-md bg-muted border border-border text-sm font-mono font-bold hover:bg-muted/80 transition-colors"
            >
              +
            </button>
          </div>
        </div>

        {/* Bid / Ask / Last */}
        {(bid != null || ask != null || last != null) && (
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            {bid != null && (
              <div>
                <span className="text-[10px] uppercase tracking-wider">Bid</span>{" "}
                <span className="font-mono tabular-nums">${bid.toFixed(2)}</span>
              </div>
            )}
            {ask != null && (
              <div>
                <span className="text-[10px] uppercase tracking-wider">Ask</span>{" "}
                <span className="font-mono tabular-nums">${ask.toFixed(2)}</span>
              </div>
            )}
            {last != null && (
              <div>
                <span className="text-[10px] uppercase tracking-wider">Last</span>{" "}
                <span className="font-mono tabular-nums">${last.toFixed(2)}</span>
              </div>
            )}
          </div>
        )}

        {/* Estimated order value */}
        {quantity > 0 && currentPrice != null && (
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Est. Value</span>
            <span className="font-mono tabular-nums font-medium">
              ${(quantity * currentPrice).toLocaleString("en-US", {
                minimumFractionDigits: 2,
                maximumFractionDigits: 2,
              })}
            </span>
          </div>
        )}

        {/* Order Preview */}
        <OrderPreview
          quantity={quantity}
          price={effectivePrice}
          direction={direction}
        />

        {/* Error / Success */}
        {error && (
          <div className="text-xs text-red-400 bg-red-400/10 rounded-md px-3 py-2">
            {error}
          </div>
        )}
        {success && (
          <div className="text-xs text-emerald-400 bg-emerald-400/10 rounded-md px-3 py-2">
            {success}
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={submitting}
          className={`w-full py-2.5 rounded-md text-sm font-semibold transition-colors ${
            direction === "buy"
              ? "bg-emerald-500 hover:bg-emerald-400 text-white"
              : "bg-red-500 hover:bg-red-400 text-white"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
          ) : (
            submitLabel
          )}
        </button>
      </form>
    </div>
  );
}
