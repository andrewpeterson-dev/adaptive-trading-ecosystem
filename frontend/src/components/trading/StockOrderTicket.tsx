"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Loader2, ShieldAlert } from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { useTradeStore } from "@/stores/trade-store";
import { OrderPreview } from "./OrderPreview";

type Direction = "buy" | "sell";
type OrderType = "market" | "limit" | "stop" | "stop_limit";
type InputMode = "shares" | "dollars";

interface ExecutionResponse {
  executed?: boolean;
  blocked?: boolean;
  mode?: string;
  symbol?: string;
  quantity?: number;
  resolved_quantity?: number;
  price?: number;
  order_id?: string;
  id?: string;
}

const ORDER_TYPES: { value: OrderType; label: string }[] = [
  { value: "market", label: "Market" },
  { value: "limit", label: "Limit" },
  { value: "stop", label: "Stop" },
  { value: "stop_limit", label: "Stop-Limit" },
];

function formatCurrency(value: number | null | undefined): string {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

interface StockOrderTicketProps {
  onOrderPlaced: () => void;
  isPaperMode?: boolean;
}

export function StockOrderTicket({ onOrderPlaced, isPaperMode }: StockOrderTicketProps) {
  const symbol = useTradeStore((state) => state.symbol);
  const quote = useTradeStore((state) => state.quote);
  const account = useTradeStore((state) => state.account);
  const { toast } = useToast();

  const [direction, setDirection] = useState<Direction>("buy");
  const [orderType, setOrderType] = useState<OrderType>("market");
  const [inputMode, setInputMode] = useState<InputMode>("shares");
  const [quantity, setQuantity] = useState("10");
  const [dollarAmount, setDollarAmount] = useState("1000");
  const [limitPrice, setLimitPrice] = useState("");
  const [stopPrice, setStopPrice] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [awaitingConfirmation, setAwaitingConfirmation] = useState(false);
  const [triedSubmit, setTriedSubmit] = useState(false);
  const [feedback, setFeedback] = useState<{
    status: "idle" | "pending" | "filled" | "error";
    message: string;
  }>({ status: "idle", message: "" });

  const currentPrice = quote?.price ?? quote?.last ?? null;
  const numericQuantity = Number(quantity) || 0;
  const numericDollarAmount = Number(dollarAmount) || 0;
  const numericLimitPrice = Number(limitPrice) || 0;
  const numericStopPrice = Number(stopPrice) || 0;

  const needsLimit = orderType === "limit" || orderType === "stop_limit";
  const needsStop = orderType === "stop" || orderType === "stop_limit";

  useEffect(() => {
    setAwaitingConfirmation(false);
    setFeedback({ status: "idle", message: "" });
  }, [symbol, direction, orderType, inputMode, quantity, dollarAmount, limitPrice, stopPrice]);

  const effectivePrice = useMemo(() => {
    if (orderType === "limit" || orderType === "stop_limit") {
      return numericLimitPrice > 0 ? numericLimitPrice : currentPrice;
    }
    if (orderType === "stop") {
      return numericStopPrice > 0 ? numericStopPrice : currentPrice;
    }
    return currentPrice;
  }, [currentPrice, numericLimitPrice, numericStopPrice, orderType]);

  const resolvedQuantity = useMemo(() => {
    if (inputMode === "shares") return Math.floor(numericQuantity);
    if (!effectivePrice || effectivePrice <= 0) return 0;
    return Math.floor(numericDollarAmount / effectivePrice);
  }, [effectivePrice, inputMode, numericDollarAmount, numericQuantity]);

  const estimatedValue = useMemo(() => {
    if (!effectivePrice || resolvedQuantity <= 0) return null;
    return effectivePrice * resolvedQuantity;
  }, [effectivePrice, resolvedQuantity]);

  const buyingPowerAfter = useMemo(() => {
    if (!account || estimatedValue == null) return null;
    return direction === "buy"
      ? account.buying_power - estimatedValue
      : account.buying_power + estimatedValue;
  }, [account, direction, estimatedValue]);

  const validationErrors = useMemo(() => {
    const errors: Record<string, string> = {};

    if (!symbol.trim()) errors.symbol = "Select a symbol first";
    if (inputMode === "shares" && numericQuantity <= 0) errors.quantity = "Enter a share quantity";
    if (inputMode === "dollars" && numericDollarAmount <= 0) errors.quantity = "Enter a dollar amount";
    if (resolvedQuantity <= 0) errors.quantity = "Not enough notional for one share";
    if (needsLimit && numericLimitPrice <= 0) errors.limitPrice = "Enter a valid limit price";
    if (needsStop && numericStopPrice <= 0) errors.stopPrice = "Enter a valid stop price";
    if (direction === "buy" && account && estimatedValue != null && estimatedValue > account.buying_power) {
      errors.buyingPower = `Insufficient buying power (${formatCurrency(account.buying_power)} available)`;
    }

    return errors;
  }, [
    account,
    direction,
    estimatedValue,
    inputMode,
    needsLimit,
    needsStop,
    numericDollarAmount,
    numericLimitPrice,
    numericQuantity,
    numericStopPrice,
    resolvedQuantity,
    symbol,
  ]);

  const riskNote = useMemo(() => {
    if (estimatedValue == null || !account) {
      return "Load a live quote to preview buying power impact and trade risk.";
    }
    if (estimatedValue > account.buying_power * 0.2) {
      return "Large order relative to available buying power. Review position concentration before sending.";
    }
    if (!needsStop) {
      return "No stop trigger is attached to this order. Downside control remains manual until you place an exit.";
    }
    return "Order size is within a normal range and includes a defined trigger price.";
  }, [account, estimatedValue, needsStop]);

  const reviewDisabled = Object.keys(validationErrors).length > 0 || submitting;

  const submitLabel =
    inputMode === "dollars"
      ? `${direction === "buy" ? "Buy" : "Sell"} ${formatCurrency(numericDollarAmount)}`
      : `${direction === "buy" ? "Buy" : "Sell"} ${resolvedQuantity} shares`;

  const executeOrder = async () => {
    setSubmitting(true);
    setFeedback({ status: "idle", message: "" });

    try {
      const response = await apiFetch<ExecutionResponse>("/api/trading/execute", {
        method: "POST",
        body: JSON.stringify({
          symbol,
          direction: direction === "buy" ? "long" : "short",
          quantity: inputMode === "shares" ? resolvedQuantity : 0,
          dollar_amount: inputMode === "dollars" ? numericDollarAmount : null,
          strength: 1.0,
          model_name: "manual",
          order_type: orderType,
          limit_price: needsLimit ? numericLimitPrice : null,
          stop_price: needsStop ? numericStopPrice : null,
          user_confirmed: true,
        }),
      });

      const executionStatus = response.mode === "live" ? "pending" : "filled";
      const executionMessage =
        executionStatus === "pending"
          ? `${submitLabel} is working in the market. Monitor routing feedback for fills.`
          : `${submitLabel} on ${symbol} filled${response.price ? ` at ${formatCurrency(response.price)}` : ""}.`;

      setFeedback({ status: executionStatus, message: executionMessage });
      toast(executionMessage, executionStatus === "filled" ? "success" : "info");
      setAwaitingConfirmation(false);
      onOrderPlaced();
    } catch (error) {
      const message = error instanceof Error ? error.message : "Order failed";
      setFeedback({ status: "error", message });
      toast(`Order failed: ${message}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Order Ticket
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Stage validated stock orders, review capital impact, then confirm before submit.
          </p>
        </div>
        {isPaperMode && <span className="app-pill text-[11px]">Paper</span>}
      </div>

      <form
        className="space-y-4"
        onSubmit={(event) => {
          event.preventDefault();
          setTriedSubmit(true);
          if (!reviewDisabled) {
            setAwaitingConfirmation(true);
          }
        }}
      >
        <div className="app-segmented">
          <button
            type="button"
            onClick={() => setDirection("buy")}
            className={`app-segment ${
              direction === "buy" ? "app-toggle-active !bg-emerald-600 !text-white !border-emerald-600" : ""
            }`}
          >
            Buy
          </button>
          <button
            type="button"
            onClick={() => setDirection("sell")}
            className={`app-segment ${
              direction === "sell" ? "app-toggle-active !bg-red-600 !text-white !border-red-600" : ""
            }`}
          >
            Sell
          </button>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Order Type
            </span>
            <select
              value={orderType}
              onChange={(event) => setOrderType(event.target.value as OrderType)}
              className="app-select"
            >
              {ORDER_TYPES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Input Mode
            </span>
            <div className="app-segmented">
              {(["shares", "dollars"] as InputMode[]).map((mode) => (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setInputMode(mode)}
                  className={`app-segment ${inputMode === mode ? "app-toggle-active" : ""}`}
                >
                  {mode === "shares" ? "Shares" : "Dollars"}
                </button>
              ))}
            </div>
          </label>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="space-y-2">
            <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {inputMode === "shares" ? "Quantity" : "Dollar Amount"}
            </span>
            <input
              type="number"
              min="0"
              step={inputMode === "shares" ? "1" : "100"}
              value={inputMode === "shares" ? quantity : dollarAmount}
              onChange={(event) =>
                inputMode === "shares"
                  ? setQuantity(event.target.value)
                  : setDollarAmount(event.target.value)
              }
              className="app-input font-mono"
            />
          </label>

          <div className="rounded-[22px] border border-border/70 bg-muted/18 px-4 py-3">
            <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              Estimated Fill
            </p>
            <p className="mt-2 font-mono text-lg font-semibold text-foreground">
              {formatCurrency(effectivePrice)}
            </p>
            <p className="mt-1 text-xs text-muted-foreground">
              Resolves to {resolvedQuantity > 0 ? resolvedQuantity : 0} shares
            </p>
          </div>
        </div>

        {(needsLimit || needsStop) && (
          <div className="grid gap-4 sm:grid-cols-2">
            {needsLimit && (
              <label className="space-y-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Limit Price
                </span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={limitPrice}
                  onChange={(event) => setLimitPrice(event.target.value)}
                  className="app-input font-mono"
                />
              </label>
            )}
            {needsStop && (
              <label className="space-y-2">
                <span className="text-[10px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
                  Stop Price
                </span>
                <input
                  type="number"
                  min="0"
                  step="0.01"
                  value={stopPrice}
                  onChange={(event) => setStopPrice(event.target.value)}
                  className="app-input font-mono"
                />
              </label>
            )}
          </div>
        )}

        <OrderPreview
          quantity={resolvedQuantity}
          price={effectivePrice}
          direction={direction}
          symbol={symbol}
        />

        <div className="rounded-[22px] border border-border/70 bg-muted/18 px-4 py-4">
          <div className="flex items-start gap-3">
            <ShieldAlert className="mt-0.5 h-4 w-4 text-amber-300" />
            <div className="space-y-2 text-sm">
              <p className="font-medium text-foreground">Pre-trade check</p>
              <p className="text-muted-foreground">{riskNote}</p>
              <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                <span>Estimated notional: {formatCurrency(estimatedValue)}</span>
                <span>Buying power after: {formatCurrency(buyingPowerAfter)}</span>
              </div>
            </div>
          </div>
        </div>

        {triedSubmit && Object.keys(validationErrors).length > 0 && (
          <div className="rounded-[22px] border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-100">
            <div className="flex items-start gap-3">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div className="space-y-1">
                {Object.values(validationErrors).map((message) => (
                  <p key={message}>{message}</p>
                ))}
              </div>
            </div>
          </div>
        )}

        {awaitingConfirmation && (
          <div className="rounded-[22px] border border-primary/25 bg-primary/10 px-4 py-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-sm font-semibold text-foreground">Confirm trade</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {submitLabel} {symbol} using a {orderType.replace("_", "-")} order.
                </p>
              </div>
              <Clock3 className="h-4 w-4 text-primary" />
            </div>
            <div className="mt-4 flex flex-wrap gap-2">
              <Button type="button" variant="primary" size="sm" onClick={executeOrder} disabled={submitting}>
                {submitting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                Confirm Order
              </Button>
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={() => setAwaitingConfirmation(false)}
                disabled={submitting}
              >
                Edit
              </Button>
            </div>
          </div>
        )}

        {feedback.status !== "idle" && (
          <div
            className={`rounded-[22px] border px-4 py-4 text-sm ${
              feedback.status === "filled"
                ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-100"
                : feedback.status === "pending"
                  ? "border-amber-500/25 bg-amber-500/10 text-amber-100"
                  : "border-red-500/25 bg-red-500/10 text-red-100"
            }`}
          >
            <div className="flex items-center gap-2 font-semibold uppercase tracking-[0.16em]">
              {feedback.status}
            </div>
            <p className="mt-2 normal-case tracking-normal">{feedback.message}</p>
          </div>
        )}

        <div className="sticky bottom-0 bg-card/95 backdrop-blur-sm border-t border-border/50 pt-3 -mx-4 px-4 pb-1">
          <Button type="submit" variant="primary" className="w-full" disabled={reviewDisabled}>
            Review Order
          </Button>
        </div>
      </form>
    </div>
  );
}
