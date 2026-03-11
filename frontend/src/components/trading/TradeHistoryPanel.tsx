"use client";

import React, { useState, useMemo, useCallback } from "react";
import { Clock, Bot, Info, ChevronLeft, ChevronRight } from "lucide-react";
import { useTradeStore } from "@/stores/trade-store";
import type { Trade, TradeFilter } from "@/types/trading";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const PAGE_SIZE = 15;
const SYMBOL_FILTER_THRESHOLD = 10;

const FILTER_TABS: { label: string; value: TradeFilter }[] = [
  { label: "All", value: "all" },
  { label: "Stocks", value: "stocks" },
  { label: "Options", value: "options" },
  { label: "Buys", value: "buys" },
  { label: "Sells", value: "sells" },
  { label: "Manual", value: "manual" },
  { label: "Bot", value: "bot" },
];

const COLUMNS = [
  "Date/Time",
  "Type",
  "Symbol",
  "Side",
  "Order Type",
  "Qty",
  "Price",
  "Total",
  "Status",
  "P&L",
  "Source",
] as const;

const SKELETON_WIDTHS = [80, 40, 64, 36, 52, 32, 56, 64, 52, 56, 56];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTradeDate(iso: string | null | undefined): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  const months = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
  ];
  const month = months[d.getMonth()];
  const day = d.getDate();
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${month} ${day}, ${hours}:${minutes}`;
}

function formatCurrency(value: number | null | undefined): string {
  if (value == null) return "\u2014";
  return value.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

function isBuyDirection(dir: string): boolean {
  return dir === "buy" || dir === "long";
}

function isOptionTrade(t: Trade): boolean {
  return t.asset_type === "option" || !!t.contract_symbol;
}

/** Build compact option descriptor like "AAPL 150C 03/21" */
function optionDescriptor(t: Trade): string {
  const underlying = t.underlying || t.symbol;
  const strike = t.strike != null ? t.strike : "?";
  const typeChar = t.option_type === "put" ? "P" : "C";
  let expShort = "";
  if (t.expiration) {
    const d = new Date(t.expiration);
    if (!isNaN(d.getTime())) {
      expShort = `${String(d.getMonth() + 1).padStart(2, "0")}/${String(
        d.getDate()
      ).padStart(2, "0")}`;
    } else {
      expShort = t.expiration;
    }
  }
  return `${underlying} ${strike}${typeChar} ${expShort}`.trim();
}

function computeTotalValue(t: Trade): number | null {
  const price = t.filled_price ?? t.entry_price ?? t.limit_price;
  if (price == null || t.quantity == null) return t.total_value ?? null;
  if (t.total_value != null) return t.total_value;
  const multiplier = isOptionTrade(t) ? 100 : 1;
  return Math.abs(t.quantity) * price * multiplier;
}

function sortKey(t: Trade): string {
  return t.filled_at || t.submitted_at || "";
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  filled: "text-emerald-400 bg-emerald-400/10",
  rejected: "text-red-400 bg-red-400/10",
  pending: "text-yellow-400 bg-yellow-400/10",
  cancelled: "text-muted-foreground bg-muted/50",
  canceled: "text-muted-foreground bg-muted/50",
  partial: "text-amber-400 bg-amber-400/10",
};

function StatusBadge({ status }: { status: string }) {
  const style = STATUS_STYLES[status] || "text-muted-foreground bg-muted/50";
  return (
    <span className={`text-xs font-medium px-1.5 py-0.5 rounded capitalize ${style}`}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Asset type badge
// ---------------------------------------------------------------------------

function AssetTypeBadge({ type }: { type: string }) {
  if (type === "option") {
    return (
      <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400">
        Option
      </span>
    );
  }
  return (
    <span className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-muted/50 text-muted-foreground">
      Stock
    </span>
  );
}

// ---------------------------------------------------------------------------
// Source display
// ---------------------------------------------------------------------------

function SourceCell({ trade }: { trade: Trade }) {
  const botName = trade.bot_name;
  if (botName) {
    return (
      <span className="inline-flex items-center gap-1 text-xs font-medium px-1.5 py-0.5 rounded bg-violet-500/10 text-violet-400">
        <Bot className="h-3 w-3" />
        {botName}
      </span>
    );
  }
  const source = trade.source || "manual";
  return (
    <span className="text-xs text-muted-foreground capitalize">{source}</span>
  );
}

// ---------------------------------------------------------------------------
// Bot explanation tooltip
// ---------------------------------------------------------------------------

function BotExplanationIcon({ explanation }: { explanation: string }) {
  const [show, setShow] = useState(false);

  return (
    <span
      className="relative inline-flex ml-1"
      onMouseEnter={() => setShow(true)}
      onMouseLeave={() => setShow(false)}
    >
      <Info className="h-3 w-3 text-muted-foreground/50 hover:text-muted-foreground cursor-help transition-colors" />
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-30 w-64 px-3 py-2 rounded-lg bg-popover border border-border shadow-lg text-xs text-foreground leading-relaxed pointer-events-none">
          {explanation}
          <div className="absolute top-full left-1/2 -translate-x-1/2 -mt-px w-2 h-2 bg-popover border-r border-b border-border rotate-45" />
        </div>
      )}
    </span>
  );
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
// Trade row
// ---------------------------------------------------------------------------

function TradeRow({
  trade,
  highlighted,
  onSelect,
}: {
  trade: Trade;
  highlighted: boolean;
  onSelect: () => void;
}) {
  const isOption = isOptionTrade(trade);
  const isBuy = isBuyDirection(trade.direction);
  const price = trade.filled_price ?? trade.entry_price;
  const total = computeTotalValue(trade);
  const pnl = trade.pnl;
  const hasPnl = pnl != null && pnl !== 0;
  const pnlIsProfit = (pnl ?? 0) >= 0;
  const dateStr = trade.filled_at || trade.submitted_at;

  return (
    <tr
      onClick={onSelect}
      className={`border-b border-border/50 hover:bg-muted/30 transition-colors cursor-pointer ${
        highlighted ? "border-l-2 border-l-primary bg-muted/20" : "border-l-2 border-l-transparent"
      }`}
    >
      {/* Date/Time */}
      <td className="py-2.5 px-4 text-xs text-muted-foreground font-mono tabular-nums whitespace-nowrap">
        {formatTradeDate(dateStr)}
      </td>

      {/* Asset Type */}
      <td className="py-2.5 px-4">
        <AssetTypeBadge type={isOption ? "option" : "stock"} />
      </td>

      {/* Symbol / Contract */}
      <td className="py-2.5 px-4">
        <span className="font-mono font-semibold text-sm">
          {isOption ? optionDescriptor(trade) : trade.symbol}
        </span>
        {isOption && trade.contract_symbol && (
          <div className="text-[10px] font-mono text-muted-foreground/50 mt-0.5 truncate max-w-[140px]">
            {trade.contract_symbol}
          </div>
        )}
      </td>

      {/* Side */}
      <td className="py-2.5 px-4">
        <span
          className={`text-xs font-semibold ${
            isBuy ? "text-emerald-400" : "text-red-400"
          }`}
        >
          {isBuy ? "BUY" : "SELL"}
        </span>
      </td>

      {/* Order Type */}
      <td className="py-2.5 px-4 text-xs text-muted-foreground capitalize whitespace-nowrap">
        {trade.order_type || "\u2014"}
      </td>

      {/* Qty */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {trade.quantity != null ? Math.abs(trade.quantity) : "\u2014"}
      </td>

      {/* Price */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(price)}
      </td>

      {/* Total Value */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(total)}
      </td>

      {/* Status */}
      <td className="py-2.5 px-4">
        <StatusBadge status={trade.status || "filled"} />
      </td>

      {/* P&L */}
      <td
        className={`py-2.5 px-4 font-mono tabular-nums font-medium ${
          hasPnl
            ? pnlIsProfit
              ? "text-emerald-400"
              : "text-red-400"
            : "text-muted-foreground"
        }`}
      >
        {hasPnl
          ? `${pnlIsProfit ? "+" : ""}${formatCurrency(pnl)}`
          : "\u2014"}
      </td>

      {/* Source */}
      <td className="py-2.5 px-4">
        <div className="flex items-center">
          <SourceCell trade={trade} />
          {trade.bot_explanation && (
            <BotExplanationIcon explanation={trade.bot_explanation} />
          )}
        </div>
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TradeHistoryPanel() {
  const { trades, loading, highlightedTradeId, setHighlightedTradeId } =
    useTradeStore();
  const [filter, setFilter] = useState<TradeFilter>("all");
  const [page, setPage] = useState(0);
  const [symbolSearch, setSymbolSearch] = useState("");

  const handleFilterChange = useCallback((tab: TradeFilter) => {
    setFilter(tab);
    setPage(0);
  }, []);

  // ---- Filtering & sorting ----
  const filtered = useMemo(() => {
    let list = [...trades];

    // Sort newest first
    list.sort((a, b) => sortKey(b).localeCompare(sortKey(a)));

    // Apply category filter
    switch (filter) {
      case "stocks":
        list = list.filter((t) => !isOptionTrade(t));
        break;
      case "options":
        list = list.filter((t) => isOptionTrade(t));
        break;
      case "buys":
        list = list.filter((t) => isBuyDirection(t.direction));
        break;
      case "sells":
        list = list.filter((t) => !isBuyDirection(t.direction));
        break;
      case "manual":
        list = list.filter((t) => !t.bot_name && (t.source === "manual" || !t.source));
        break;
      case "bot":
        list = list.filter((t) => !!t.bot_name || (t.source && t.source !== "manual"));
        break;
    }

    // Apply symbol search
    if (symbolSearch.trim()) {
      const q = symbolSearch.trim().toUpperCase();
      list = list.filter(
        (t) =>
          t.symbol.toUpperCase().includes(q) ||
          (t.underlying && t.underlying.toUpperCase().includes(q)) ||
          (t.contract_symbol && t.contract_symbol.toUpperCase().includes(q))
      );
    }

    return list;
  }, [trades, filter, symbolSearch]);

  const totalPages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const safePage = Math.min(page, totalPages - 1);
  const paged = filtered.slice(safePage * PAGE_SIZE, (safePage + 1) * PAGE_SIZE);

  const showSymbolSearch = trades.length > SYMBOL_FILTER_THRESHOLD;
  const isLoading = loading && trades.length === 0;

  // ---- Header ----
  const header = (
    <div className="px-4 py-3 border-b border-border/50 flex items-center justify-between gap-3">
      <div className="flex items-center gap-2 shrink-0">
        <h3 className="text-sm font-semibold">Trade History</h3>
        <span className="text-[10px] font-mono text-muted-foreground bg-muted/50 px-1.5 py-0.5 rounded">
          {isLoading ? "--" : trades.length}
        </span>
      </div>

      {!isLoading && trades.length > 0 && (
        <div className="flex items-center gap-2 overflow-x-auto">
          {showSymbolSearch && (
            <input
              type="text"
              value={symbolSearch}
              onChange={(e) => {
                setSymbolSearch(e.target.value);
                setPage(0);
              }}
              placeholder="Filter symbol..."
              className="h-6 w-24 text-xs rounded border border-border/50 bg-muted/30 px-2 placeholder:text-muted-foreground/40 focus:outline-none focus:ring-1 focus:ring-primary/30 font-mono"
            />
          )}
          <div className="flex items-center gap-0.5">
            {FILTER_TABS.map((tab) => (
              <button
                key={tab.value}
                onClick={() => handleFilterChange(tab.value)}
                className={`text-xs font-medium px-2 py-1 rounded transition-colors whitespace-nowrap ${
                  filter === tab.value
                    ? "bg-muted text-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
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
              {COLUMNS.map((col, i) => (
                <th key={i} className="py-2 px-4 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[0, 1, 2, 3, 4].map((i) => (
              <SkeletonRow key={i} cols={SKELETON_WIDTHS} />
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  // ---- Empty state ----
  if (trades.length === 0) {
    return (
      <div className="rounded-xl border border-border/50 bg-card overflow-hidden">
        {header}
        <div className="py-6 flex flex-col items-center gap-2 text-center px-4">
          <div className="inline-flex items-center justify-center h-8 w-8 rounded-full bg-muted/50 border border-border/50">
            <Clock className="h-3.5 w-3.5 text-muted-foreground/50" />
          </div>
          <div>
            <div className="text-sm font-medium text-muted-foreground">
              No trades yet
            </div>
            <div className="text-xs text-muted-foreground/60 mt-0.5">
              Executed trades will appear here
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
            No trades match the current filter
          </div>
          <button
            onClick={() => {
              setFilter("all");
              setSymbolSearch("");
              setPage(0);
            }}
            className="text-xs text-primary hover:underline"
          >
            Clear filters
          </button>
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
              {COLUMNS.map((col, i) => (
                <th key={i} className="py-2 px-4 whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {paged.map((trade, i) => (
              <TradeRow
                key={trade.id || `${trade.symbol}-${i}`}
                trade={trade}
                highlighted={highlightedTradeId === trade.id}
                onSelect={() =>
                  setHighlightedTradeId(
                    highlightedTradeId === trade.id ? null : trade.id
                  )
                }
              />
            ))}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="px-4 py-2.5 border-t border-border/50 flex items-center justify-between text-xs text-muted-foreground">
          <span>
            {safePage * PAGE_SIZE + 1}&ndash;
            {Math.min((safePage + 1) * PAGE_SIZE, filtered.length)} of{" "}
            {filtered.length}
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage(Math.max(0, safePage - 1))}
              disabled={safePage === 0}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-border/50 hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="h-3 w-3" />
              Prev
            </button>
            <span className="px-1 tabular-nums font-mono">
              {safePage + 1}/{totalPages}
            </span>
            <button
              onClick={() => setPage(Math.min(totalPages - 1, safePage + 1))}
              disabled={safePage >= totalPages - 1}
              className="inline-flex items-center gap-1 px-2.5 py-1 rounded border border-border/50 hover:bg-muted transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="h-3 w-3" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
