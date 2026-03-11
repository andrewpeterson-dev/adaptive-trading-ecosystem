"use client";

import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import {
  Settings,
  BarChart3,
  Loader2,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Info,
} from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import { useToast } from "@/components/ui/toast";
import { apiFetch } from "@/lib/api/client";
import type { OptionContract } from "@/types/trading";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface OptionsChainResponse {
  expirations: string[];
  strikes: number[];
  contracts: OptionContract[];
  selected_expiration?: string;
  selectedExpiration?: string;
}

type OptionDirection =
  | "buy_to_open"
  | "sell_to_close"
  | "sell_to_open"
  | "buy_to_close";

type OptionSide = "call" | "put";

const DIRECTION_LABELS: Record<OptionDirection, string> = {
  buy_to_open: "Buy to Open",
  sell_to_close: "Sell to Close",
  sell_to_open: "Sell to Open",
  buy_to_close: "Buy to Close",
};

const DIRECTION_VERB: Record<OptionDirection, string> = {
  buy_to_open: "Buy",
  sell_to_close: "Sell",
  sell_to_open: "Sell",
  buy_to_close: "Buy",
};

const DIRECTION_PAST: Record<OptionDirection, string> = {
  buy_to_open: "Bought",
  sell_to_close: "Sold",
  sell_to_open: "Sold",
  buy_to_close: "Bought",
};

function isBuyDirection(d: OptionDirection): boolean {
  return d === "buy_to_open" || d === "buy_to_close";
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

function fmt(
  n: number | undefined | null,
  decimals = 2,
  fallback = "--"
): string {
  if (n == null || isNaN(n)) return fallback;
  return n.toFixed(decimals);
}

function fmtUsd(n: number | null | undefined, fallback = "--"): string {
  if (n == null || isNaN(n)) return fallback;
  return n.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function fmtPct(n: number | undefined | null, fallback = "--"): string {
  if (n == null || isNaN(n)) return fallback;
  return (n * 100).toFixed(1) + "%";
}

function daysUntil(dateStr: string): number {
  const target = new Date(dateStr + "T16:00:00");
  const now = new Date();
  const diff = target.getTime() - now.getTime();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

function formatExpShort(dateStr: string): string {
  const d = new Date(dateStr + "T12:00:00");
  return d.toLocaleDateString("en-US", { month: "2-digit", day: "2-digit" });
}

/* ------------------------------------------------------------------ */
/*  No-Data State                                                      */
/* ------------------------------------------------------------------ */

function OptionsNoData({ symbol }: { symbol: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-card p-5">
      <div className="flex items-center gap-2 mb-3">
        <Settings className="h-4 w-4 text-muted-foreground" />
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          Options Trading
        </span>
      </div>

      <div className="flex items-center gap-1.5 mb-3">
        <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          Underlying:{" "}
          <span className="font-medium text-foreground">{symbol}</span>
        </span>
      </div>

      <div className="rounded-lg border border-border/50 bg-muted/30 p-3">
        <div className="flex items-start gap-2 mb-2">
          <Info className="h-3.5 w-3.5 text-muted-foreground mt-0.5 shrink-0" />
          <div>
            <p className="text-xs font-medium text-foreground mb-1">
              No live options chain available
            </p>
            <p className="text-[11px] text-muted-foreground mb-2">
              When the market data API returns contracts for{" "}
              <span className="font-medium text-foreground">{symbol}</span>,
              this panel will show:
            </p>
          </div>
        </div>
        <ul className="space-y-1 text-[11px] text-muted-foreground ml-5">
          <li className="flex items-start gap-1.5">
            <span className="text-muted-foreground/60 mt-px">&#8226;</span>
            Options chain by expiry with bid/ask
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-muted-foreground/60 mt-px">&#8226;</span>
            Strike selector and Greeks
          </li>
          <li className="flex items-start gap-1.5">
            <span className="text-muted-foreground/60 mt-px">&#8226;</span>
            Order entry with portfolio impact preview
          </li>
        </ul>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Expiration Selector                                                */
/* ------------------------------------------------------------------ */

function ExpirationSelector({
  expirations,
  selected,
  onSelect,
}: {
  expirations: string[];
  selected: string;
  onSelect: (exp: string) => void;
}) {
  const scrollRef = useRef<HTMLDivElement>(null);

  const scroll = (dir: "left" | "right") => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({
      left: dir === "left" ? -120 : 120,
      behavior: "smooth",
    });
  };

  return (
    <div>
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
        Expiration
      </div>
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => scroll("left")}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors flex-shrink-0"
        >
          <ChevronLeft className="h-3.5 w-3.5" />
        </button>
        <div
          ref={scrollRef}
          className="flex gap-1 overflow-x-auto scrollbar-hide flex-1"
        >
          {expirations.map((exp) => {
            const dte = daysUntil(exp);
            return (
              <button
                key={exp}
                type="button"
                onClick={() => onSelect(exp)}
                className={`px-2.5 py-1.5 rounded-md text-xs font-medium whitespace-nowrap transition-colors flex-shrink-0 ${
                  selected === exp
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {exp}
                <span className="ml-1 text-[10px] text-muted-foreground">
                  ({dte}d)
                </span>
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() => scroll("right")}
          className="p-1 rounded-md text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors flex-shrink-0"
        >
          <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Greeks Display                                                     */
/* ------------------------------------------------------------------ */

function GreeksDisplay({ contract }: { contract: OptionContract }) {
  const greeks = [
    { label: "Delta", value: fmt(contract.delta, 4) },
    { label: "Gamma", value: fmt(contract.gamma, 4) },
    { label: "Theta", value: fmt(contract.theta, 4) },
    { label: "Vega", value: fmt(contract.vega, 4) },
    { label: "IV", value: fmtPct(contract.implied_volatility) },
  ];

  return (
    <div className="grid grid-cols-5 gap-2">
      {greeks.map((g) => (
        <div key={g.label} className="text-center">
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
            {g.label}
          </div>
          <div className="text-xs font-mono tabular-nums mt-0.5">
            {g.value}
          </div>
        </div>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Contract Summary Card                                              */
/* ------------------------------------------------------------------ */

function ContractSummary({
  contract,
  direction,
  quantity,
}: {
  contract: OptionContract;
  direction: OptionDirection;
  quantity: number;
}) {
  const bid = contract.bid;
  const ask = contract.ask;
  const last = contract.last;
  const hasPricing = bid != null && ask != null;
  const mid = hasPricing ? (bid + ask) / 2 : null;
  const isBuy = isBuyDirection(direction);
  const premium = isBuy ? ask : bid;
  const totalPremium = premium != null ? premium * quantity * 100 : null;
  const dte = daysUntil(contract.expiration);

  // Breakeven
  const breakeven = useMemo(() => {
    if (premium == null) return null;
    if (direction === "buy_to_open") {
      return contract.type === "call"
        ? contract.strike + premium
        : contract.strike - premium;
    }
    if (direction === "sell_to_open") {
      return contract.type === "call"
        ? contract.strike + premium
        : contract.strike - premium;
    }
    return null;
  }, [contract.strike, contract.type, direction, premium]);

  // Max profit / loss
  const maxProfit = useMemo((): string => {
    if (premium == null) return "--";
    if (direction === "buy_to_open") {
      return contract.type === "call"
        ? "Unlimited"
        : "$" + fmtUsd((contract.strike - premium) * quantity * 100);
    }
    if (direction === "sell_to_open") {
      return "$" + fmtUsd(premium * quantity * 100);
    }
    return "--";
  }, [contract.strike, contract.type, direction, premium, quantity]);

  const maxLoss = useMemo((): string => {
    if (premium == null) return "--";
    if (direction === "buy_to_open") {
      return "$" + fmtUsd(premium * quantity * 100);
    }
    if (direction === "sell_to_open") {
      return contract.type === "call"
        ? "Unlimited"
        : "$" + fmtUsd((contract.strike * 100 - premium * 100) * quantity);
    }
    return "--";
  }, [contract.strike, contract.type, direction, premium, quantity]);

  return (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-3 space-y-2.5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">
          {contract.underlying} {contract.expiration}{" "}
          {contract.strike}
          {contract.type === "call" ? "C" : "P"}
        </span>
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          {DIRECTION_LABELS[direction]}
        </span>
      </div>

      {/* Pricing row */}
      <div className="grid grid-cols-4 gap-2 text-xs text-muted-foreground">
        <div>
          <span className="text-[10px] uppercase tracking-wider block">
            Bid
          </span>
          <span className="font-mono tabular-nums">
            {bid != null ? `$${fmt(bid)}` : "\u2014"}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider block">
            Ask
          </span>
          <span className="font-mono tabular-nums">
            {ask != null ? `$${fmt(ask)}` : "\u2014"}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider block">
            Mid
          </span>
          <span className="font-mono tabular-nums">
            {mid != null ? `$${fmt(mid)}` : "\u2014"}
          </span>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider block">
            Last
          </span>
          <span className="font-mono tabular-nums">
            {last != null ? `$${fmt(last)}` : "\u2014"}
          </span>
        </div>
      </div>

      {/* Contract details */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Multiplier</span>
          <span className="font-mono tabular-nums">100</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">DTE</span>
          <span className="font-mono tabular-nums">{dte}</span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">
            Per Contract
          </span>
          <span className="font-mono tabular-nums">
            {premium != null ? `$${fmt(premium)}` : "\u2014"}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">
            {isBuy ? "Total Cost" : "Total Credit"}
          </span>
          <span className="font-mono tabular-nums font-medium">
            {totalPremium != null ? `$${fmtUsd(totalPremium)}` : "\u2014"}
          </span>
        </div>
      </div>

      {/* Risk profile */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs pt-1 border-t border-border/30">
        {breakeven != null && (
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Breakeven</span>
            <span className="font-mono tabular-nums font-medium">
              ${fmt(breakeven)}
            </span>
          </div>
        )}
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Max Profit</span>
          <span
            className={`font-mono tabular-nums font-medium ${
              maxProfit === "Unlimited" ? "text-emerald-400" : ""
            }`}
          >
            {maxProfit}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-muted-foreground">Max Loss</span>
          <span
            className={`font-mono tabular-nums font-medium ${
              maxLoss === "Unlimited" ? "text-red-400" : ""
            }`}
          >
            {maxLoss}
          </span>
        </div>
      </div>

      {/* Greeks */}
      {(contract.delta != null || contract.gamma != null) && (
        <div className="pt-1 border-t border-border/30">
          <GreeksDisplay contract={contract} />
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Order Preview (Portfolio Impact)                                   */
/* ------------------------------------------------------------------ */

function OrderPreview({
  contract,
  direction,
  quantity,
  cashAvailable,
  portfolioValue,
}: {
  contract: OptionContract;
  direction: OptionDirection;
  quantity: number;
  cashAvailable: number | null;
  portfolioValue: number | null;
}) {
  const isBuy = isBuyDirection(direction);
  const premium = isBuy ? contract.ask : contract.bid;
  if (premium == null) return null;

  const totalPremium = premium * quantity * 100;
  const remainingCash =
    cashAvailable != null
      ? isBuy
        ? cashAvailable - totalPremium
        : cashAvailable + totalPremium
      : null;
  const pctOfPortfolio =
    portfolioValue != null && portfolioValue > 0
      ? (totalPremium / portfolioValue) * 100
      : null;
  const breakeven =
    direction === "buy_to_open" || direction === "sell_to_open"
      ? contract.type === "call"
        ? contract.strike + premium
        : contract.strike - premium
      : null;

  return (
    <div className="rounded-lg border border-border/50 bg-muted/20 p-3 space-y-1.5">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1">
        Order Preview
      </div>

      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">
          {isBuy ? "Total Debit" : "Total Credit"}
        </span>
        <span
          className={`font-mono tabular-nums font-medium ${
            isBuy ? "text-red-400" : "text-emerald-400"
          }`}
        >
          {isBuy ? "-" : "+"}${fmtUsd(totalPremium)}
        </span>
      </div>

      {remainingCash != null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Remaining Cash</span>
          <span
            className={`font-mono tabular-nums ${
              remainingCash < 0 ? "text-red-400 font-medium" : ""
            }`}
          >
            ${fmtUsd(remainingCash)}
          </span>
        </div>
      )}

      {pctOfPortfolio != null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">% of Portfolio</span>
          <span className="font-mono tabular-nums">
            {pctOfPortfolio.toFixed(1)}%
          </span>
        </div>
      )}

      {breakeven != null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Breakeven</span>
          <span className="font-mono tabular-nums">${fmt(breakeven)}</span>
        </div>
      )}

      <p className="text-[10px] text-muted-foreground/70 pt-1">
        {quantity} contract{quantity !== 1 ? "s" : ""} x 100 shares/contract ={" "}
        {(quantity * 100).toLocaleString()} shares equivalent
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Validation                                                         */
/* ------------------------------------------------------------------ */

interface ValidationResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

function validateOrder(
  selectedStrike: number | null,
  selectedContract: OptionContract | null,
  direction: OptionDirection,
  quantity: number,
  cashAvailable: number | null
): ValidationResult {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (selectedStrike == null) {
    errors.push("Select a strike price");
  }

  if (quantity < 1) {
    errors.push("Quantity must be at least 1");
  }

  if (selectedContract && isBuyDirection(direction) && cashAvailable != null) {
    const premium = selectedContract.ask;
    if (premium != null) {
      const totalCost = premium * quantity * 100;
      if (totalCost > cashAvailable) {
        warnings.push(
          `Order cost $${fmtUsd(totalCost)} exceeds available cash $${fmtUsd(
            cashAvailable
          )}`
        );
      }
    }
  }

  return { valid: errors.length === 0, errors, warnings };
}

/* ------------------------------------------------------------------ */
/*  Options Panel (main export)                                        */
/* ------------------------------------------------------------------ */

export function OptionsPanel() {
  const { symbol, account } = useTradeStore();
  const { toast } = useToast();

  // Data state
  const [hasOptionsData, setHasOptionsData] = useState(false);
  const [chainData, setChainData] = useState<OptionsChainResponse | null>(null);
  const [chainLoading, setChainLoading] = useState(true);

  // Selection state
  const [selectedExpiration, setSelectedExpiration] = useState("");
  const [selectedStrike, setSelectedStrike] = useState<number | null>(null);
  const [optionSide, setOptionSide] = useState<OptionSide>("call");
  const [liquidityFilter, setLiquidityFilter] = useState<"all" | "active">("active");
  const [direction, setDirection] = useState<OptionDirection>("buy_to_open");
  const [quantity, setQuantity] = useState(1);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  /* ---- Fetch options chain ---- */
  const fetchChain = useCallback(async (expiration?: string) => {
    setChainLoading(true);
    setError(null);
    setSelectedStrike(null);

    try {
      const query = new URLSearchParams({ symbol });
      if (expiration) {
        query.set("expiration", expiration);
      }

      const data = await apiFetch<OptionsChainResponse>(
        `/api/trading/options-chain?${query.toString()}`
      );
      if (data && data.expirations && data.expirations.length > 0) {
        setChainData(data);
        setHasOptionsData(true);
        setSelectedExpiration(
          data.selected_expiration ??
            data.selectedExpiration ??
            expiration ??
            data.expirations[0]
        );
      } else {
        setHasOptionsData(false);
        setChainData(null);
      }
    } catch (err) {
      setHasOptionsData(false);
      setChainData(null);
      setError(err instanceof Error ? err.message : "Failed to load options chain");
    } finally {
      setChainLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    setHasOptionsData(false);
    setChainData(null);
    setSelectedExpiration("");
    fetchChain();
  }, [fetchChain]);

  // Reset strike when expiration changes
  useEffect(() => {
    setSelectedStrike(null);
  }, [selectedExpiration]);

  useEffect(() => {
    if (!selectedExpiration) return;
    if (
      chainData?.selected_expiration === selectedExpiration ||
      chainData?.selectedExpiration === selectedExpiration
    ) {
      return;
    }
    fetchChain(selectedExpiration);
  }, [
    chainData?.selected_expiration,
    chainData?.selectedExpiration,
    fetchChain,
    selectedExpiration,
  ]);

  /* ---- Derived data ---- */
  const contracts = useMemo(
    () =>
      chainData?.contracts.filter((c) => c.expiration === selectedExpiration) ?? [],
    [chainData, selectedExpiration]
  );

  const filteredContracts = useMemo(
    () =>
      contracts
        .filter((contract) => contract.type === optionSide)
        .filter((contract) => {
          if (liquidityFilter === "all") return true;
          return (contract.volume ?? 0) > 0 || (contract.open_interest ?? 0) > 0;
        })
        .sort((left, right) => left.strike - right.strike),
    [contracts, liquidityFilter, optionSide]
  );

  useEffect(() => {
    if (selectedStrike == null) return;
    if (!filteredContracts.some((contract) => contract.strike === selectedStrike)) {
      setSelectedStrike(null);
    }
  }, [filteredContracts, selectedStrike]);

  const selectedContract = useMemo(
    () =>
      selectedStrike != null
        ? filteredContracts.find(
            (c) => c.strike === selectedStrike && c.type === optionSide
          ) ?? null
        : null,
    [filteredContracts, selectedStrike, optionSide]
  );

  const cashAvailable = account?.cash ?? null;
  const portfolioValue = account?.portfolio_value ?? null;

  const validation = useMemo(
    () =>
      validateOrder(
        selectedStrike,
        selectedContract,
        direction,
        quantity,
        cashAvailable
      ),
    [selectedStrike, selectedContract, direction, quantity, cashAvailable]
  );

  const canSubmit =
    validation.valid && selectedContract != null && !submitting;

  /* ---- Submit ---- */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canSubmit || !selectedContract) return;

    setError(null);
    setSubmitting(true);

    const label = `${DIRECTION_PAST[direction]} ${quantity} ${selectedContract.underlying} ${selectedContract.expiration} ${selectedContract.strike}${selectedContract.type === "call" ? "C" : "P"}`;

    try {
      await apiFetch("/api/trading/execute-option", {
        method: "POST",
        body: JSON.stringify({
          contract_symbol: selectedContract.symbol,
          underlying: selectedContract.underlying,
          expiration: selectedContract.expiration,
          strike: selectedContract.strike,
          option_type: selectedContract.type,
          direction,
          quantity,
          user_confirmed: true,
        }),
      });
      toast(label, "success");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Order failed";
      setError(msg);
      toast(`Order failed: ${msg}`, "error");
    } finally {
      setSubmitting(false);
    }
  };

  const decrementQty = () => setQuantity((q) => Math.max(1, q - 1));
  const incrementQty = () => setQuantity((q) => q + 1);

  /* ---- Submit button label ---- */
  const submitLabel = useMemo(() => {
    if (!selectedContract) return "Select a strike";
    const verb = DIRECTION_VERB[direction];
    const exp = formatExpShort(selectedContract.expiration);
    return `${verb} ${quantity} ${selectedContract.underlying} ${selectedContract.strike}${selectedContract.type === "call" ? "C" : "P"} ${exp}`;
  }, [selectedContract, direction, quantity]);

  const submitColor = isBuyDirection(direction)
    ? "bg-emerald-500 hover:bg-emerald-400"
    : "bg-red-500 hover:bg-red-400";

  /* ---- Loading state ---- */
  if (chainLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-5 flex items-center justify-center min-h-[200px]">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  /* ---- No data state ---- */
  if (!hasOptionsData || !chainData) {
    return <OptionsNoData symbol={symbol} />;
  }

  /* ---- Main panel ---- */
  return (
    <div className="rounded-xl border border-border/50 bg-card p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Settings className="h-4 w-4 text-muted-foreground" />
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          Options Trading
        </span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {/* Expiration selector */}
        <ExpirationSelector
          expirations={chainData.expirations}
          selected={selectedExpiration}
          onSelect={setSelectedExpiration}
        />

        {/* Call / Put toggle */}
        <div>
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Option Type
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setOptionSide("call")}
              className={`py-2 rounded-md text-sm font-semibold transition-colors ${
                optionSide === "call"
                  ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                  : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
              }`}
            >
              Call
            </button>
            <button
              type="button"
              onClick={() => setOptionSide("put")}
              className={`py-2 rounded-md text-sm font-semibold transition-colors ${
                optionSide === "put"
                  ? "bg-red-500/20 text-red-400 border border-red-500/30"
                  : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
              }`}
            >
              Put
            </button>
          </div>
        </div>

        {/* Direction toggle (2x2 grid) */}
        <div>
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Direction
          </div>
          <div className="grid grid-cols-2 gap-1.5">
            {(
              [
                "buy_to_open",
                "sell_to_open",
                "buy_to_close",
                "sell_to_close",
              ] as OptionDirection[]
            ).map((d) => {
              const active = direction === d;
              const buy = isBuyDirection(d);
              return (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDirection(d)}
                  className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                    active
                      ? buy
                        ? "bg-emerald-500/20 text-emerald-400 border border-emerald-500/30"
                        : "bg-red-500/20 text-red-400 border border-red-500/30"
                      : "bg-muted text-muted-foreground border border-border/50 hover:text-foreground"
                  }`}
                >
                  {DIRECTION_LABELS[d]}
                </button>
              );
            })}
          </div>
        </div>

        {/* Chain table */}
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
              Chain
            </div>
            <div className="flex items-center gap-1 rounded-full border border-border/60 bg-muted/35 p-1">
              {(["active", "all"] as const).map((value) => (
                <button
                  key={value}
                  type="button"
                  onClick={() => setLiquidityFilter(value)}
                  className={`rounded-full px-3 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] transition-colors ${
                    liquidityFilter === value
                      ? "bg-foreground text-background"
                      : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {value === "active" ? "Active only" : "All strikes"}
                </button>
              ))}
            </div>
          </div>
          {filteredContracts.length === 0 ? (
            <div className="rounded-2xl border border-border/60 bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
              No {optionSide} contracts match the current expiration and liquidity filters.
            </div>
          ) : (
            <div className="overflow-hidden rounded-3xl border border-border/60">
              <div className="max-h-72 overflow-auto">
                <table className="app-table min-w-full text-xs">
                  <thead>
                    <tr>
                      <th>Strike</th>
                      <th>Bid</th>
                      <th>Ask</th>
                      <th>Last</th>
                      <th>IV</th>
                      <th>Volume</th>
                      <th>OI</th>
                      <th>Delta</th>
                      <th>Gamma</th>
                      <th>Theta</th>
                      <th>Vega</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredContracts.map((contract) => (
                      <tr
                        key={`${contract.symbol}-${contract.strike}`}
                        onClick={() => setSelectedStrike(contract.strike)}
                        className={`cursor-pointer transition-colors ${
                          selectedStrike === contract.strike ? "bg-muted/35" : "hover:bg-muted/25"
                        }`}
                      >
                        <td className="font-mono font-semibold tabular-nums">
                          {contract.strike.toFixed(contract.strike % 1 === 0 ? 0 : 2)}
                        </td>
                        <td className="font-mono tabular-nums">{fmt(contract.bid)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.ask)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.last)}</td>
                        <td className="font-mono tabular-nums">{fmtPct(contract.implied_volatility)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.volume, 0)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.open_interest, 0)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.delta, 4)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.gamma, 4)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.theta, 4)}</td>
                        <td className="font-mono tabular-nums">{fmt(contract.vega, 4)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          {selectedStrike == null && filteredContracts.length > 0 && (
            <p className="mt-2 text-[10px] text-muted-foreground/60">
              Select a row to stage that contract in the order form below.
            </p>
          )}
        </div>

        {/* Quantity */}
        <div>
          <label className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest block mb-1.5">
            Contracts
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
              onChange={(e) =>
                setQuantity(Math.max(1, parseInt(e.target.value) || 1))
              }
              min="1"
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

        {/* Contract summary */}
        {selectedContract && (
          <ContractSummary
            contract={selectedContract}
            direction={direction}
            quantity={quantity}
          />
        )}

        {/* Order preview (portfolio impact) */}
        {selectedContract && (
          <OrderPreview
            contract={selectedContract}
            direction={direction}
            quantity={quantity}
            cashAvailable={cashAvailable}
            portfolioValue={portfolioValue}
          />
        )}

        {/* Validation messages */}
        {validation.warnings.length > 0 && (
          <div className="flex items-start gap-2 text-xs text-amber-400 bg-amber-400/10 rounded-md px-3 py-2">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <div className="space-y-0.5">
              {validation.warnings.map((w, i) => (
                <p key={i}>{w}</p>
              ))}
            </div>
          </div>
        )}

        {/* Inline error */}
        {error && (
          <div className="flex items-start gap-2 text-xs text-red-400 bg-red-400/10 rounded-md px-3 py-2">
            <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
            <p>{error}</p>
          </div>
        )}

        {/* Submit */}
        <button
          type="submit"
          disabled={!canSubmit}
          className={`w-full py-2.5 rounded-md text-sm font-semibold transition-colors text-white ${submitColor} disabled:opacity-50 disabled:cursor-not-allowed`}
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
