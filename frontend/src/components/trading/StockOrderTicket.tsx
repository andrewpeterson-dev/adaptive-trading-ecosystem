"use client";

import React, { useState, useCallback, useEffect, useMemo, useRef } from "react";
import { Loader2 } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import { apiFetch } from "@/lib/api/client";
import { useToast } from "@/components/ui/toast";
import { OrderPreview } from "./OrderPreview";

type Direction = "buy" | "sell";
type OrderType = "market" | "limit" | "stop" | "stop_limit";
type InputMode = "shares" | "dollars";

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

function fmt(value: number): string {
  return value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

export function StockOrderTicket({ onOrderPlaced, isPaperMode }: StockOrderTicketProps) {
  const { symbol, quote, account } = useTradeStore();
  const { toast } = useToast();

  const [direction, setDirection] = useState<Direction>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [quantity, setQuantity] = useState(0);
  const [dollarAmount, setDollarAmount] = useState(0);
  const [inputMode, setInputMode] = useState<InputMode>("shares");
  const [limitPrice, setLimitPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [touched, setTouched] = useState<Record<string, boolean>>({});

  const successTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const prevOrderType = useRef<OrderType>(orderType);
  const prevDirection = useRef<Direction>(direction);

  // Derived prices
  const currentPrice = quote?.price ?? quote?.last ?? null;
  const bid = quote?.bid;
  const ask = quote?.ask;
  const last = quote?.last ?? quote?.price;
  const spread = bid != null && ask != null ? ask - bid : null;

  const needsLimit = orderType === "limit" || orderType === "stop_limit";
  const needsStop = orderType === "stop" || orderType === "stop_limit";

  // Pre-fill limit price when switching to limit-type order
  useEffect(() => {
    const wasLimit =
      prevOrderType.current === "limit" || prevOrderType.current === "stop_limit";
    const isLimit = needsLimit;

    if (isLimit && !wasLimit) {
      // Pre-fill with ask (buy) or bid (sell)
      const prefill =
        direction === "buy"
          ? ask ?? currentPrice
          : bid ?? currentPrice;
      if (prefill != null && (!limitPrice || parseFloat(limitPrice) <= 0)) {
        setLimitPrice(prefill.toFixed(2));
      }
    }
    prevOrderType.current = orderType;
  }, [orderType, needsLimit, direction, ask, bid, currentPrice, limitPrice]);

  // Update limit price prefill when direction changes while on a limit order
  useEffect(() => {
    if (prevDirection.current !== direction && needsLimit) {
      const prefill =
        direction === "buy"
          ? ask ?? currentPrice
          : bid ?? currentPrice;
      if (prefill != null) {
        setLimitPrice(prefill.toFixed(2));
      }
    }
    prevDirection.current = direction;
  }, [direction, needsLimit, ask, bid, currentPrice]);

  // Reset fields when symbol changes
  useEffect(() => {
    setQuantity(0);
    setDollarAmount(0);
    setLimitPrice("");
    setStopPrice("");
    setError(null);
    setSuccess(null);
    setTouched({});
  }, [symbol]);

  // Auto-clear success after 5s
  useEffect(() => {
    if (success) {
      successTimer.current = setTimeout(() => setSuccess(null), 5000);
      return () => {
        if (successTimer.current) clearTimeout(successTimer.current);
      };
    }
  }, [success]);

  // Effective price for estimation
  const effectivePrice = useMemo(() => {
    if (needsLimit) {
      const lp = parseFloat(limitPrice);
      return !isNaN(lp) && lp > 0 ? lp : currentPrice;
    }
    if (orderType === "stop") {
      const sp = parseFloat(stopPrice);
      return !isNaN(sp) && sp > 0 ? sp : currentPrice;
    }
    return currentPrice;
  }, [orderType, needsLimit, limitPrice, stopPrice, currentPrice]);

  // Compute actual quantity (resolve dollar mode)
  const resolvedQuantity = useMemo(() => {
    if (inputMode === "dollars" && effectivePrice && effectivePrice > 0) {
      return Math.floor(dollarAmount / effectivePrice);
    }
    return quantity;
  }, [inputMode, dollarAmount, effectivePrice, quantity]);

  // Dollar equivalent for share mode, share equivalent for dollar mode
  const secondaryDisplay = useMemo(() => {
    if (inputMode === "shares" && quantity > 0 && effectivePrice) {
      return `$${fmt(quantity * effectivePrice)}`;
    }
    if (inputMode === "dollars" && effectivePrice && effectivePrice > 0 && dollarAmount > 0) {
      const shares = Math.floor(dollarAmount / effectivePrice);
      return `${shares} share${shares !== 1 ? "s" : ""}`;
    }
    return null;
  }, [inputMode, quantity, dollarAmount, effectivePrice]);

  // Inline validation
  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {};

    if (touched.symbol && !symbol) {
      errors.symbol = "Enter a valid symbol";
    }

    if (touched.quantity) {
      if (inputMode === "shares" && quantity <= 0) {
        errors.quantity = "Enter quantity";
      }
      if (inputMode === "dollars" && dollarAmount <= 0) {
        errors.quantity = "Enter dollar amount";
      }
    }

    if (touched.limitPrice && needsLimit) {
      if (!limitPrice || parseFloat(limitPrice) <= 0) {
        errors.limitPrice = "Enter limit price";
      }
    }

    if (touched.stopPrice && needsStop) {
      if (!stopPrice || parseFloat(stopPrice) <= 0) {
        errors.stopPrice = "Enter stop price";
      }
    }

    // Buying power check
    const estimatedNotional =
      inputMode === "dollars"
        ? dollarAmount
        : resolvedQuantity > 0 && effectivePrice
          ? resolvedQuantity * effectivePrice
          : null;

    if (
      direction === "buy" &&
      estimatedNotional != null &&
      account
    ) {
      if (estimatedNotional > account.buying_power) {
        errors.buyingPower = `Insufficient buying power ($${fmt(account.buying_power)} available)`;
      }
    }

    return errors;
  }, [
    symbol,
    quantity,
    dollarAmount,
    inputMode,
    limitPrice,
    stopPrice,
    needsLimit,
    needsStop,
    direction,
    resolvedQuantity,
    effectivePrice,
    account,
    touched,
  ]);

  // Full validation for submit guard
  const canSubmit = useMemo(() => {
    if (submitting) return false;
    if (!symbol) return false;
    if (inputMode === "shares" && resolvedQuantity <= 0) return false;
    if (inputMode === "dollars" && dollarAmount <= 0) return false;
    if (needsLimit && (!limitPrice || parseFloat(limitPrice) <= 0)) return false;
    if (needsStop && (!stopPrice || parseFloat(stopPrice) <= 0)) return false;
    if (
      direction === "buy" &&
      account &&
      (
        inputMode === "dollars"
          ? dollarAmount
          : effectivePrice != null
            ? resolvedQuantity * effectivePrice
            : 0
      ) > account.buying_power
    ) {
      return false;
    }
    return true;
  }, [
    submitting,
    symbol,
    inputMode,
    dollarAmount,
    resolvedQuantity,
    needsLimit,
    needsStop,
    limitPrice,
    stopPrice,
    direction,
    effectivePrice,
    account,
  ]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    // Touch all fields
    setTouched({ symbol: true, quantity: true, limitPrice: true, stopPrice: true });

    if (!canSubmit) return;

    setSubmitting(true);
    const orderSymbol = symbol.toUpperCase();
    const orderQty = inputMode === "shares" ? resolvedQuantity : 0;
    const orderNotional = inputMode === "dollars" ? dollarAmount : null;
    const label =
      inputMode === "dollars"
        ? `${direction === "buy" ? "Buy" : "Sell"} $${fmt(dollarAmount)} ${orderSymbol}`
        : `${direction === "buy" ? "Buy" : "Sell"} ${orderQty} ${orderSymbol}`;

    try {
      await apiFetch("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol: orderSymbol,
          direction: direction === "buy" ? "long" : "short",
          quantity: orderQty,
          dollar_amount: orderNotional,
          strength: 1.0,
          model_name: "manual",
          order_type: orderType,
          limit_price: needsLimit ? parseFloat(limitPrice) : null,
          stop_price: needsStop ? parseFloat(stopPrice) : null,
          user_confirmed: true,
        }),
      });

      const successMsg = `${label} submitted`;
      setSuccess(successMsg);
      toast(successMsg, "success");
      setQuantity(0);
      setDollarAmount(0);
      setLimitPrice("");
      setStopPrice("");
      setTouched({});
      onOrderPlaced();
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Order failed";
      setError(msg);
      toast(`Order failed: ${msg}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const decrementQty = () => {
    if (inputMode === "shares") {
      setQuantity((q) => Math.max(0, q - 1));
    } else {
      setDollarAmount((d) => Math.max(0, d - 100));
    }
    setTouched((t) => ({ ...t, quantity: true }));
  };

  const incrementQty = () => {
    if (inputMode === "shares") {
      setQuantity((q) => q + 1);
    } else {
      setDollarAmount((d) => d + 100);
    }
    setTouched((t) => ({ ...t, quantity: true }));
  };

  const submitLabel =
    inputMode === "dollars" && dollarAmount > 0 && symbol
      ? `${direction === "buy" ? "Buy" : "Sell"} $${fmt(dollarAmount)} ${symbol.toUpperCase()}`
      : resolvedQuantity > 0 && symbol
        ? `${direction === "buy" ? "Buy" : "Sell"} ${resolvedQuantity} ${symbol.toUpperCase()}`
      : direction === "buy"
        ? "Buy"
        : "Sell";

  // Est. value
  const estValue =
    resolvedQuantity > 0 && effectivePrice ? resolvedQuantity * effectivePrice : null;

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
        {needsLimit && (
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
              Limit Price
            </label>
            <input
              type="number"
              value={limitPrice}
              onChange={(e) => {
                setLimitPrice(e.target.value);
                setTouched((t) => ({ ...t, limitPrice: true }));
              }}
              onBlur={() => setTouched((t) => ({ ...t, limitPrice: true }))}
              placeholder="0.00"
              min="0"
              step="0.01"
              className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            {validationErrors.limitPrice && (
              <p className="text-xs text-red-400 mt-1">{validationErrors.limitPrice}</p>
            )}
          </div>
        )}
        {needsStop && (
          <div>
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
              Stop Price
            </label>
            <input
              type="number"
              value={stopPrice}
              onChange={(e) => {
                setStopPrice(e.target.value);
                setTouched((t) => ({ ...t, stopPrice: true }));
              }}
              onBlur={() => setTouched((t) => ({ ...t, stopPrice: true }))}
              placeholder="0.00"
              min="0"
              step="0.01"
              className="w-full px-3 py-2 rounded-md bg-muted border border-border text-sm font-mono tabular-nums focus:outline-none focus:ring-2 focus:ring-ring/40"
            />
            {validationErrors.stopPrice && (
              <p className="text-xs text-red-400 mt-1">{validationErrors.stopPrice}</p>
            )}
          </div>
        )}

        {/* Quantity */}
        <div>
          <div className="flex items-center justify-between mb-1.5">
            <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              {inputMode === "shares" ? "Quantity" : "Amount"}
            </label>
            <div className="flex items-center rounded-md overflow-hidden border border-border/50">
              <button
                type="button"
                onClick={() => {
                  setInputMode("shares");
                  setDollarAmount(0);
                  setQuantity(0);
                  setTouched((t) => ({ ...t, quantity: false }));
                }}
                className={`px-2 py-0.5 text-[10px] font-semibold transition-colors ${
                  inputMode === "shares"
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Shares
              </button>
              <button
                type="button"
                onClick={() => {
                  setInputMode("dollars");
                  setDollarAmount(0);
                  setQuantity(0);
                  setTouched((t) => ({ ...t, quantity: false }));
                }}
                className={`px-2 py-0.5 text-[10px] font-semibold transition-colors ${
                  inputMode === "dollars"
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                $
              </button>
            </div>
          </div>
          <div className="flex items-center gap-0">
            <button
              type="button"
              onClick={decrementQty}
              className="px-3 py-2 rounded-l-md bg-muted border border-border text-sm font-mono font-bold hover:bg-muted/80 transition-colors"
            >
              -
            </button>
            {inputMode === "shares" ? (
              <input
                type="number"
                value={quantity}
                onChange={(e) => {
                  setQuantity(Math.max(0, parseInt(e.target.value) || 0));
                  setTouched((t) => ({ ...t, quantity: true }));
                }}
                onBlur={() => setTouched((t) => ({ ...t, quantity: true }))}
                min="0"
                step="1"
                className="flex-1 px-3 py-2 bg-muted border-y border-border text-sm font-mono tabular-nums text-center focus:outline-none focus:ring-2 focus:ring-ring/40"
              />
            ) : (
              <div className="flex-1 relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm font-mono text-muted-foreground">
                  $
                </span>
                <input
                  type="number"
                  value={dollarAmount || ""}
                  onChange={(e) => {
                    setDollarAmount(Math.max(0, parseFloat(e.target.value) || 0));
                    setTouched((t) => ({ ...t, quantity: true }));
                  }}
                  onBlur={() => setTouched((t) => ({ ...t, quantity: true }))}
                  min="0"
                  step="100"
                  placeholder="0"
                  className="w-full pl-7 pr-3 py-2 bg-muted border-y border-border text-sm font-mono tabular-nums text-center focus:outline-none focus:ring-2 focus:ring-ring/40"
                />
              </div>
            )}
            <button
              type="button"
              onClick={incrementQty}
              className="px-3 py-2 rounded-r-md bg-muted border border-border text-sm font-mono font-bold hover:bg-muted/80 transition-colors"
            >
              +
            </button>
          </div>
          {/* Secondary display */}
          {secondaryDisplay && (
            <p className="text-[11px] text-muted-foreground mt-1 text-center font-mono">
              {inputMode === "shares" ? "Est. value: " : ""}
              {secondaryDisplay}
            </p>
          )}
          {validationErrors.quantity && (
            <p className="text-xs text-red-400 mt-1">{validationErrors.quantity}</p>
          )}
        </div>

        {/* Bid / Ask / Last */}
        {(bid != null || ask != null || last != null) && (
          <div className="space-y-1">
            <div className="grid grid-cols-3 gap-2 text-center">
              {bid != null && (
                <div>
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Bid
                  </div>
                  <div className="text-xs font-mono tabular-nums font-medium">
                    ${bid.toFixed(2)}
                  </div>
                </div>
              )}
              {ask != null && (
                <div>
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Ask
                  </div>
                  <div className="text-xs font-mono tabular-nums font-medium">
                    ${ask.toFixed(2)}
                  </div>
                </div>
              )}
              {last != null && (
                <div>
                  <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wider">
                    Last
                  </div>
                  <div className="text-xs font-mono tabular-nums font-medium">
                    ${last.toFixed(2)}
                  </div>
                </div>
              )}
            </div>
            {spread != null && (
              <div className="text-center text-[10px] text-muted-foreground font-mono">
                (spread: ${spread.toFixed(2)})
              </div>
            )}
          </div>
        )}

        {/* Estimated order value */}
        {estValue != null && (
          <div className="flex justify-between text-xs">
            <span className="text-muted-foreground">Est. Value</span>
            <span className="font-mono tabular-nums font-medium">${fmt(estValue)}</span>
          </div>
        )}

        {/* Buying power warning */}
        {validationErrors.buyingPower && (
          <div className="text-xs text-amber-400 bg-amber-400/10 rounded-md px-3 py-2">
            {validationErrors.buyingPower}
          </div>
        )}

        {/* Order Preview */}
        <OrderPreview
          quantity={resolvedQuantity}
          price={effectivePrice}
          direction={direction}
          symbol={symbol}
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
          disabled={!canSubmit}
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
