"use client";

import React, { useState, useMemo, useCallback } from "react";
import {
  Loader2,
  TrendingUp,
  X,
  ChevronDown,
  Bot,
  Scissors,
  ArrowLeftRight,
} from "lucide-react";
import { apiFetch } from "@/lib/api/client";
import { useTradeStore } from "@/stores/trade-store";
import { useToast } from "@/components/ui/toast";
import type { Position } from "@/types/trading";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PositionsPanelProps {
  onClose: () => void;
}

type AssetFilter = "all" | "stocks" | "options";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function formatPnl(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${formatCurrency(value)}`;
}

function formatPnlPct(value: number): string {
  const prefix = value >= 0 ? "+" : "";
  return `${prefix}${(value * 100).toFixed(2)}%`;
}

function pnlColor(value: number): string {
  return value >= 0 ? "text-emerald-400" : "text-red-400";
}

/** Build a compact option descriptor like "AAPL 150C 03/21" */
function optionDescriptor(p: Position): string {
  const underlying = p.underlying || p.symbol;
  const strike = p.strike != null ? p.strike : "?";
  const typeChar = p.option_type === "put" ? "P" : "C";
  let expShort = "";
  if (p.expiration) {
    const d = new Date(p.expiration);
    if (!isNaN(d.getTime())) {
      expShort = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(
        d.getDate()
      ).padStart(2, "0")}`;
    } else {
      expShort = p.expiration;
    }
  }
  return `${underlying} ${strike}${typeChar} ${expShort}`.trim();
}

function isOptionPosition(p: Position): boolean {
  return p.asset_type === "option" || !!p.contract_symbol;
}

// ---------------------------------------------------------------------------
// Skeleton row
// ---------------------------------------------------------------------------

function SkeletonRow({ cols }: { cols: number[] }) {
  return (
    <tr className="border-b border-border/50">
      {cols.map((w, i) => (
        <td key={i} className="py-3 px-4">
          <div
            className="h-4 animate-pulse bg-muted rounded"
            style={{ width: `${w}px` }}
          />
        </td>
      ))}
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Source badge
// ---------------------------------------------------------------------------

function SourceBadge({ position }: { position: Position }) {
  const botName = position.bot_name;
  if (botName) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400">
        <Bot className="h-3 w-3" />
        {botName}
      </span>
    );
  }
  const source = position.source || "manual";
  return (
    <span className="text-xs text-muted-foreground capitalize">{source}</span>
  );
}

// ---------------------------------------------------------------------------
// Action dropdown
// ---------------------------------------------------------------------------

function ActionDropdown({
  position,
  closing,
  onClosePosition,
}: {
  position: Position;
  closing: boolean;
  onClosePosition: () => void;
}) {
  const [open, setOpen] = useState(false);

  return (
    <div className="relative flex items-center gap-1">
      {/* Primary close button */}
      <button
        onClick={onClosePosition}
        disabled={closing}
        className="text-xs text-muted-foreground hover:text-foreground border border-transparent hover:border-border/50 rounded-md px-2 py-1 transition-colors flex items-center gap-1 disabled:opacity-40"
      >
        {closing ? (
          <Loader2 className="h-3 w-3 animate-spin" />
        ) : (
          <X className="h-3 w-3" />
        )}
        Close
      </button>

      {/* More actions */}
      <button
        onClick={() => setOpen(!open)}
        className="text-muted-foreground hover:text-foreground rounded p-0.5 transition-colors"
      >
        <ChevronDown className="h-3.5 w-3.5" />
      </button>

      {open && (
        <>
          {/* Backdrop */}
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          {/* Dropdown */}
          <div className="absolute right-0 top-full mt-1 z-20 bg-card border border-border/50 rounded-lg shadow-lg py-1 min-w-[120px]">
            <button
              disabled
              className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground/50 flex items-center gap-2 cursor-not-allowed"
              title="Reduce position (coming soon)"
            >
              <Scissors className="h-3 w-3" />
              Reduce
            </button>
            <button
              disabled
              className="w-full text-left px-3 py-1.5 text-xs text-muted-foreground/50 flex items-center gap-2 cursor-not-allowed"
              title="Reverse position (coming soon)"
            >
              <ArrowLeftRight className="h-3 w-3" />
              Reverse
            </button>
          </div>
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stock position row
// ---------------------------------------------------------------------------

function StockPositionRow({
  position,
  closing,
  onClose,
  onSymbolClick,
}: {
  position: Position;
  closing: boolean;
  onClose: () => void;
  onSymbolClick: () => void;
}) {
  const pnl = position.unrealized_pnl ?? 0;
  const pnlPct = position.unrealized_pnl_pct ?? 0;
  const color = pnlColor(pnl);

  return (
    <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors">
      <td className="py-2.5 px-4">
        <button
          onClick={onSymbolClick}
          className="font-mono font-semibold text-sm hover:text-primary transition-colors"
        >
          {position.symbol}
        </button>
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {position.quantity != null ? position.quantity : "\u2014"}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.avg_entry_price)}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.current_price)}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.market_value)}
      </td>
      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
        {position.unrealized_pnl != null ? formatPnl(pnl) : "\u2014"}
      </td>
      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
        {position.unrealized_pnl_pct != null ? formatPnlPct(pnlPct) : "\u2014"}
      </td>
      <td className="py-2.5 px-4">
        <span
          className={`text-xs font-medium px-1.5 py-0.5 rounded ${
            position.side === "long"
              ? "text-emerald-400 bg-emerald-400/10"
              : "text-red-400 bg-red-400/10"
          }`}
        >
          {position.side?.toUpperCase() || "\u2014"}
        </span>
      </td>
      <td className="py-2.5 px-4">
        <SourceBadge position={position} />
      </td>
      <td className="py-2.5 px-4">
        <ActionDropdown
          position={position}
          closing={closing}
          onClosePosition={onClose}
        />
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Option position row
// ---------------------------------------------------------------------------

function OptionPositionRow({
  position,
  closing,
  onClose,
  onSymbolClick,
}: {
  position: Position;
  closing: boolean;
  onClose: () => void;
  onSymbolClick: () => void;
}) {
  const pnl = position.unrealized_pnl ?? 0;
  const pnlPct = position.unrealized_pnl_pct ?? 0;
  const color = pnlColor(pnl);
  const descriptor = optionDescriptor(position);

  return (
    <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors">
      <td className="py-2.5 px-4">
        <button
          onClick={onSymbolClick}
          className="font-mono font-semibold text-sm hover:text-primary transition-colors text-left"
        >
          {descriptor}
        </button>
        {position.contract_symbol && (
          <div className="text-[10px] font-mono text-muted-foreground/60 mt-0.5 truncate max-w-[160px]">
            {position.contract_symbol}
          </div>
        )}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {position.quantity != null ? position.quantity : "\u2014"}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.avg_premium ?? position.avg_entry_price)}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.current_mark ?? position.current_price)}
      </td>
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.market_value)}
      </td>
      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
        {position.unrealized_pnl != null ? formatPnl(pnl) : "\u2014"}
      </td>
      <td className={`py-2.5 px-4 font-mono tabular-nums font-medium ${color}`}>
        {position.unrealized_pnl_pct != null ? formatPnlPct(pnlPct) : "\u2014"}
      </td>
      <td className="py-2.5 px-4">
        <div className="flex flex-col gap-0.5">
          <span
            className={`text-xs font-medium px-1.5 py-0.5 rounded w-fit ${
              position.option_type === "call"
                ? "text-emerald-400 bg-emerald-400/10"
                : "text-red-400 bg-red-400/10"
            }`}
          >
            {position.option_type === "put" ? "PUT" : "CALL"}
          </span>
          {position.expiration && (
            <span className="text-[10px] text-muted-foreground/60 font-mono">
              Exp {position.expiration}
            </span>
          )}
        </div>
      </td>
      <td className="py-2.5 px-4">
        <SourceBadge position={position} />
      </td>
      <td className="py-2.5 px-4">
        <ActionDropdown
          position={position}
          closing={closing}
          onClosePosition={onClose}
        />
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Header columns (shared between stock & option views)
// ---------------------------------------------------------------------------

const STOCK_COLUMNS = [
  "Symbol",
  "Qty",
  "Avg Entry",
  "Current",
  "Mkt Value",
  "P&L ($)",
  "P&L (%)",
  "Side",
  "Source",
  "",
] as const;

const OPTION_COLUMNS = [
  "Contract",
  "Qty",
  "Avg Premium",
  "Current Mark",
  "Mkt Value",
  "P&L ($)",
  "P&L (%)",
  "Type / Exp",
  "Source",
  "",
] as const;

const SKELETON_WIDTHS = [48, 32, 64, 64, 80, 64, 48, 40, 56, 48];

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function PositionsPanel({ onClose }: PositionsPanelProps) {
  const { positions, loading, setSymbol } = useTradeStore();
  const { toast } = useToast();
  const [closingId, setClosingId] = useState<string | null>(null);
  const [assetFilter, setAssetFilter] = useState<AssetFilter>("all");

  // ---- Filtering ----
  const { filtered, stockCount, optionCount } = useMemo(() => {
    let stocks = 0;
    let options = 0;
    const result: Position[] = [];

    for (const p of positions) {
      const isOption = isOptionPosition(p);
      if (isOption) options++;
      else stocks++;

      if (assetFilter === "all") {
        result.push(p);
      } else if (assetFilter === "options" && isOption) {
        result.push(p);
      } else if (assetFilter === "stocks" && !isOption) {
        result.push(p);
      }
    }

    return { filtered: result, stockCount: stocks, optionCount: options };
  }, [positions, assetFilter]);

  // Determine which column headers to show based on what's visible
  const hasOptions = filtered.some(isOptionPosition);
  const hasStocks = filtered.some((p) => !isOptionPosition(p));
  const mixedView = hasOptions && hasStocks;
  // Use option columns if ALL visible are options, stock columns if all stocks,
  // otherwise stock columns (options rows will adapt)
  const showOptionHeaders = hasOptions && !hasStocks;
  const columns = showOptionHeaders ? OPTION_COLUMNS : STOCK_COLUMNS;

  // ---- Close position handler ----
  const handleClosePosition = useCallback(
    async (position: Position) => {
      const posId =
        position.contract_symbol || position.symbol;
      setClosingId(posId);
      try {
        await apiFetch("/api/trading/execute", {
          method: "POST",
          body: JSON.stringify({
            symbol: position.symbol,
            direction: position.side === "long" ? "short" : "long",
            quantity: Math.abs(position.quantity),
            strength: 1.0,
            model_name: "manual",
            order_type: "market",
            limit_price: position.current_price,
            user_confirmed: true,
          }),
        });
        toast(
          `Closed ${position.symbol} position (${Math.abs(position.quantity)} ${
            isOptionPosition(position) ? "contracts" : "shares"
          })`,
          "success"
        );
      } catch {
        toast(`Failed to close ${position.symbol} position`, "error");
      } finally {
        setClosingId(null);
      }
    },
    [toast]
  );

  const isLoading = loading && positions.length === 0;

  // ---- Filter pills ----
  const filterTabs: { label: string; value: AssetFilter; count?: number }[] = [
    { label: "All", value: "all" },
    { label: "Stocks", value: "stocks", count: stockCount },
    { label: "Options", value: "options", count: optionCount },
  ];

  // Only show filter if we have both types
  const showFilter = stockCount > 0 && optionCount > 0;

  // ---- Header ----
  const header = (
    <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Open Positions</h3>
        <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
          {isLoading ? "--" : positions.length}
        </span>
      </div>
      {showFilter && !isLoading && (
        <div className="flex items-center gap-1">
          {filterTabs.map((tab) => (
            <button
              key={tab.value}
              onClick={() => setAssetFilter(tab.value)}
              className={`text-xs font-medium px-2.5 py-1 rounded transition-colors ${
                assetFilter === tab.value
                  ? "bg-muted text-foreground"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
              }`}
            >
              {tab.label}
              {tab.count != null && tab.count > 0 && (
                <span className="ml-1 text-[10px] opacity-60">{tab.count}</span>
              )}
            </button>
          ))}
        </div>
      )}
    </div>
  );

  // ---- Loading state ----
  if (isLoading) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        {header}
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              {STOCK_COLUMNS.map((col, i) => (
                <th key={i} className="py-2 px-4">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2].map((i) => (
              <SkeletonRow key={i} cols={SKELETON_WIDTHS} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // ---- Empty state ----
  if (positions.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        {header}
        <div className="py-6 flex flex-col items-center gap-2 text-center px-4 max-h-[80px] justify-center">
          <div className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-muted/50 border border-border/50">
            <TrendingUp className="h-3.5 w-3.5 text-muted-foreground/50" />
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground">
              No open positions
            </div>
            <div className="text-xs text-muted-foreground/60 mt-0.5">
              Place a trade or run a strategy to see positions here
            </div>
          </div>
        </div>
      </div>
    );
  }

  // ---- Filtered empty ----
  if (filtered.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        {header}
        <div className="py-6 flex flex-col items-center gap-2 text-center px-4">
          <div className="text-sm text-muted-foreground">
            No {assetFilter} positions
          </div>
        </div>
      </div>
    );
  }

  // ---- Main render ----
  return (
    <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
      {header}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr className="bg-muted/30 text-xs text-muted-foreground uppercase tracking-wider">
              {columns.map((col, i) => (
                <th key={i} className="py-2 px-4 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const isOption = isOptionPosition(p);
              const posId = p.contract_symbol || p.symbol;
              const closing = closingId === posId;
              const onSymbolClick = () =>
                setSymbol(p.underlying || p.symbol);

              if (isOption) {
                return (
                  <OptionPositionRow
                    key={posId}
                    position={p}
                    closing={closing}
                    onClose={() => handleClosePosition(p)}
                    onSymbolClick={onSymbolClick}
                  />
                );
              }

              return (
                <StockPositionRow
                  key={posId}
                  position={p}
                  closing={closing}
                  onClose={() => handleClosePosition(p)}
                  onSymbolClick={onSymbolClick}
                />
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
