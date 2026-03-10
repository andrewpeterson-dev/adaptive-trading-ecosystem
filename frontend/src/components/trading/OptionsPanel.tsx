"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import { Settings, BarChart3, TrendingUp, Loader2, ChevronLeft, ChevronRight } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import { apiFetch } from "@/lib/api/client";
import type { OptionContract } from "@/types/trading";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface OptionsChainResponse {
  expirations: string[];
  strikes: number[];
  contracts: OptionContract[];
}

type OptionDirection = "buy_to_open" | "sell_to_close";
type OptionSide = "call" | "put";

/* ------------------------------------------------------------------ */
/*  Helper: format a number with fallback                              */
/* ------------------------------------------------------------------ */

function fmt(n: number | undefined | null, decimals = 2, fallback = "--"): string {
  if (n == null || isNaN(n)) return fallback;
  return n.toFixed(decimals);
}

function fmtPct(n: number | undefined | null, fallback = "--"): string {
  if (n == null || isNaN(n)) return fallback;
  return (n * 100).toFixed(1) + "%";
}

/* ------------------------------------------------------------------ */
/*  No-Data State (State A)                                            */
/* ------------------------------------------------------------------ */

function OptionsNoData({ symbol }: { symbol: string }) {
  return (
    <div className="rounded-xl border border-border/50 bg-card p-5">
      {/* Header */}
      <div className="flex items-center gap-2 mb-4">
        <Settings className="h-4 w-4 text-muted-foreground" />
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          Options Trading
        </span>
      </div>

      {/* Underlying label */}
      <div className="flex items-center gap-1.5 mb-4">
        <BarChart3 className="h-3.5 w-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground">
          Showing underlying: <span className="font-medium text-foreground">{symbol}</span>
        </span>
      </div>

      {/* Info card */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-5">
        <p className="text-sm font-medium text-primary mb-3">
          Options market data not yet connected
        </p>
        <p className="text-xs text-muted-foreground mb-3">
          When options data is available, you&apos;ll see:
        </p>
        <ul className="space-y-1.5 text-xs text-muted-foreground">
          <li className="flex items-start gap-2">
            <span className="text-primary mt-0.5">&#8226;</span>
            Options chain by expiry
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary mt-0.5">&#8226;</span>
            Strike selector
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary mt-0.5">&#8226;</span>
            Greeks (delta, gamma, theta, vega, IV)
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary mt-0.5">&#8226;</span>
            Bid/Ask/Mark pricing
          </li>
          <li className="flex items-start gap-2">
            <span className="text-primary mt-0.5">&#8226;</span>
            Order entry
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
    scrollRef.current.scrollBy({ left: dir === "left" ? -120 : 120, behavior: "smooth" });
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
        <div ref={scrollRef} className="flex gap-1 overflow-x-auto scrollbar-hide flex-1">
          {expirations.map((exp) => (
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
            </button>
          ))}
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
/*  Strike Row                                                         */
/* ------------------------------------------------------------------ */

function StrikeRow({
  strike,
  callContract,
  putContract,
  selected,
  onSelect,
}: {
  strike: number;
  callContract?: OptionContract;
  putContract?: OptionContract;
  selected: boolean;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`grid grid-cols-5 gap-1 px-2 py-1.5 rounded-md text-xs transition-colors w-full ${
        selected
          ? "bg-muted/80 border border-border/50"
          : "hover:bg-muted/40"
      }`}
    >
      {/* Call bid/ask */}
      <span className="font-mono tabular-nums text-emerald-400 text-right">
        {fmt(callContract?.bid)}
      </span>
      <span className="font-mono tabular-nums text-muted-foreground text-right">
        {fmt(callContract?.ask)}
      </span>

      {/* Strike */}
      <span className="font-mono tabular-nums font-semibold text-foreground text-center">
        {strike.toFixed(strike % 1 === 0 ? 0 : 2)}
      </span>

      {/* Put bid/ask */}
      <span className="font-mono tabular-nums text-red-400 text-left">
        {fmt(putContract?.bid)}
      </span>
      <span className="font-mono tabular-nums text-muted-foreground text-left">
        {fmt(putContract?.ask)}
      </span>
    </button>
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
          <div className="text-xs font-mono tabular-nums mt-0.5">{g.value}</div>
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
  const bid = contract.bid ?? 0;
  const ask = contract.ask ?? 0;
  const mark = (bid + ask) / 2;
  const premium = direction === "buy_to_open" ? ask : bid;
  const totalCost = premium * quantity * 100;

  // Breakeven for buy-to-open
  const breakeven =
    direction === "buy_to_open"
      ? contract.type === "call"
        ? contract.strike + premium
        : contract.strike - premium
      : null;

  return (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-3 space-y-2">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium text-foreground">
          {contract.underlying} {contract.expiration} {contract.strike}
          {contract.type === "call" ? "C" : "P"}
        </span>
        <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
          {direction === "buy_to_open" ? "Buy to Open" : "Sell to Close"}
        </span>
      </div>

      {/* Pricing row */}
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <div>
          <span className="text-[10px] uppercase tracking-wider">Bid</span>{" "}
          <span className="font-mono tabular-nums">${fmt(bid)}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider">Ask</span>{" "}
          <span className="font-mono tabular-nums">${fmt(ask)}</span>
        </div>
        <div>
          <span className="text-[10px] uppercase tracking-wider">Mark</span>{" "}
          <span className="font-mono tabular-nums">${fmt(mark)}</span>
        </div>
      </div>

      {/* Cost + breakeven */}
      <div className="flex items-center justify-between text-xs">
        <div>
          <span className="text-muted-foreground">
            {direction === "buy_to_open" ? "Total Cost" : "Total Credit"}
          </span>
        </div>
        <span className="font-mono tabular-nums font-medium">
          ${totalCost.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
        </span>
      </div>
      {breakeven != null && (
        <div className="flex items-center justify-between text-xs">
          <span className="text-muted-foreground">Breakeven</span>
          <span className="font-mono tabular-nums font-medium">${fmt(breakeven)}</span>
        </div>
      )}

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
/*  Options Panel (main export)                                        */
/* ------------------------------------------------------------------ */

export function OptionsPanel() {
  const { symbol } = useTradeStore();

  // Data state
  const [hasOptionsData, setHasOptionsData] = useState(false);
  const [chainData, setChainData] = useState<OptionsChainResponse | null>(null);
  const [chainLoading, setChainLoading] = useState(true);

  // Selection state
  const [selectedExpiration, setSelectedExpiration] = useState("");
  const [selectedStrike, setSelectedStrike] = useState<number | null>(null);
  const [optionSide, setOptionSide] = useState<OptionSide>("call");
  const [direction, setDirection] = useState<OptionDirection>("buy_to_open");
  const [quantity, setQuantity] = useState(1);

  // Submit state
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  /* ---- Fetch options chain on mount / symbol change ---- */
  const fetchChain = useCallback(async () => {
    setChainLoading(true);
    setHasOptionsData(false);
    setChainData(null);
    setError(null);
    setSuccess(null);

    try {
      const data = await apiFetch<OptionsChainResponse>(
        `/api/trading/options-chain?symbol=${encodeURIComponent(symbol)}`
      );
      if (data && data.expirations && data.expirations.length > 0) {
        setChainData(data);
        setHasOptionsData(true);
        setSelectedExpiration(data.expirations[0]);
        setSelectedStrike(null);
      } else {
        setHasOptionsData(false);
      }
    } catch {
      // API doesn't exist yet -- show no-data state
      setHasOptionsData(false);
    } finally {
      setChainLoading(false);
    }
  }, [symbol]);

  useEffect(() => {
    fetchChain();
  }, [fetchChain]);

  // Reset selection when expiration changes
  useEffect(() => {
    setSelectedStrike(null);
  }, [selectedExpiration]);

  /* ---- Loading ---- */
  if (chainLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card p-5 flex items-center justify-center min-h-[200px]">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  /* ---- State A: No data ---- */
  if (!hasOptionsData || !chainData) {
    return <OptionsNoData symbol={symbol} />;
  }

  /* ---- State B: Data available ---- */
  const contracts = chainData.contracts.filter((c) => c.expiration === selectedExpiration);
  const strikes = Array.from(new Set(contracts.map((c) => c.strike))).sort((a, b) => a - b);

  const selectedContract = selectedStrike != null
    ? contracts.find((c) => c.strike === selectedStrike && c.type === optionSide) ?? null
    : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedContract) return;

    setError(null);
    setSuccess(null);
    setSubmitting(true);

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
      setSuccess(
        `${direction === "buy_to_open" ? "Bought" : "Sold"} ${quantity} ${selectedContract.underlying} ${selectedContract.expiration} ${selectedContract.strike}${selectedContract.type === "call" ? "C" : "P"}`
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Order failed");
    } finally {
      setSubmitting(false);
    }
  };

  const decrementQty = () => setQuantity((q) => Math.max(1, q - 1));
  const incrementQty = () => setQuantity((q) => q + 1);

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

        {/* Direction toggle */}
        <div>
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Direction
          </div>
          <div className="grid grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setDirection("buy_to_open")}
              className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                direction === "buy_to_open"
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              Buy to Open
            </button>
            <button
              type="button"
              onClick={() => setDirection("sell_to_close")}
              className={`py-1.5 rounded-md text-xs font-medium transition-colors ${
                direction === "sell_to_close"
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              Sell to Close
            </button>
          </div>
        </div>

        {/* Strike selector (chain view) */}
        <div>
          <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1.5">
            Strikes
          </div>
          {/* Column headers */}
          <div className="grid grid-cols-5 gap-1 px-2 mb-1 text-[10px] font-semibold text-muted-foreground uppercase tracking-widest">
            <span className="text-right">C Bid</span>
            <span className="text-right">C Ask</span>
            <span className="text-center">Strike</span>
            <span className="text-left">P Bid</span>
            <span className="text-left">P Ask</span>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-0.5">
            {strikes.map((strike) => {
              const callC = contracts.find((c) => c.strike === strike && c.type === "call");
              const putC = contracts.find((c) => c.strike === strike && c.type === "put");
              return (
                <StrikeRow
                  key={strike}
                  strike={strike}
                  callContract={callC}
                  putContract={putC}
                  selected={selectedStrike === strike}
                  onSelect={() => setSelectedStrike(strike)}
                />
              );
            })}
          </div>
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
              onChange={(e) => setQuantity(Math.max(1, parseInt(e.target.value) || 1))}
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

        {/* Contract summary card */}
        {selectedContract && (
          <ContractSummary
            contract={selectedContract}
            direction={direction}
            quantity={quantity}
          />
        )}

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
          disabled={submitting || !selectedContract}
          className={`w-full py-2.5 rounded-md text-sm font-semibold transition-colors ${
            direction === "buy_to_open"
              ? "bg-emerald-500 hover:bg-emerald-400 text-white"
              : "bg-red-500 hover:bg-red-400 text-white"
          } disabled:opacity-50 disabled:cursor-not-allowed`}
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin mx-auto" />
          ) : selectedContract ? (
            `${direction === "buy_to_open" ? "Buy" : "Sell"} ${quantity} ${selectedContract.underlying} ${selectedContract.strike}${selectedContract.type === "call" ? "C" : "P"}`
          ) : (
            "Select a strike"
          )}
        </button>
      </form>
    </div>
  );
}
