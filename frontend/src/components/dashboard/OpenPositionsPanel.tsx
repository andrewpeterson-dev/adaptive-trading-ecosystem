"use client";

import React from "react";
import { TrendingUp, ArrowUpRight, ArrowDownRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Position } from "@/types/trading";
import { EmptyState } from "@/components/ui/empty-state";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface OpenPositionsPanelProps {
  positions: Position[];
  onSelectPosition?: (symbol: string) => void;
  hideHeader?: boolean;
}

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

function positionSide(p: Position): "buy" | "sell" {
  if (p.side === "short" || p.side === "sell") return "sell";
  if (p.side === "long" || p.side === "buy") return "buy";
  return p.quantity < 0 ? "sell" : "buy";
}

// ---------------------------------------------------------------------------
// Side badge
// ---------------------------------------------------------------------------

function SideBadge({ side }: { side: "buy" | "sell" }) {
  return (
    <span
      className={cn(
        "text-xs font-semibold px-1.5 py-0.5 rounded uppercase",
        side === "buy"
          ? "text-emerald-400 bg-emerald-400/10"
          : "text-red-400 bg-red-400/10"
      )}
    >
      {side}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Table columns
// ---------------------------------------------------------------------------

const COLUMNS = [
  "Symbol",
  "Size",
  "Side",
  "Entry",
  "Current",
  "P&L",
  "Change %",
] as const;

// ---------------------------------------------------------------------------
// Position row
// ---------------------------------------------------------------------------

function PositionRow({
  position,
  onSelect,
}: {
  position: Position;
  onSelect?: () => void;
}) {
  const pnl = position.unrealized_pnl ?? 0;
  const pnlPct = position.unrealized_pnl_pct ?? 0;
  const color = pnlColor(pnl);
  const side = positionSide(position);
  const PnlIcon = pnl >= 0 ? ArrowUpRight : ArrowDownRight;

  return (
    <tr
      onClick={onSelect}
      className={cn(
        "border-b border-border/50 transition-colors",
        onSelect && "cursor-pointer hover:bg-muted/30"
      )}
    >
      {/* Symbol */}
      <td className="py-2.5 px-4">
        <span className="font-mono font-bold text-sm">{position.symbol}</span>
      </td>

      {/* Size */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {position.quantity != null ? Math.abs(position.quantity) : "\u2014"}
      </td>

      {/* Side */}
      <td className="py-2.5 px-4">
        <SideBadge side={side} />
      </td>

      {/* Entry */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.avg_entry_price)}
      </td>

      {/* Current */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(position.current_price)}
      </td>

      {/* P&L */}
      <td className={cn("py-2.5 px-4 font-mono tabular-nums font-medium", color)}>
        <span className="inline-flex items-center gap-1">
          <PnlIcon className="h-3 w-3" />
          {position.unrealized_pnl != null ? formatPnl(pnl) : "\u2014"}
        </span>
      </td>

      {/* Change % */}
      <td className={cn("py-2.5 px-4 font-mono tabular-nums font-medium", color)}>
        {position.unrealized_pnl_pct != null ? formatPnlPct(pnlPct) : "\u2014"}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function OpenPositionsPanel({
  positions,
  onSelectPosition,
  hideHeader,
}: OpenPositionsPanelProps) {
  if (positions.length === 0) {
    return (
      <div className={hideHeader ? "" : "app-table-shell"}>
        {!hideHeader && (
          <div className="app-section-header">
            <h3 className="text-sm font-semibold text-foreground">Open Positions</h3>
          </div>
        )}
        <EmptyState
          className="py-10"
          icon={<TrendingUp className="h-4 w-4 text-muted-foreground" />}
          title="Awaiting first execution"
          description="Active positions and real-time P&L will appear here"
        />
      </div>
    );
  }

  return (
    <div className={hideHeader ? "" : "app-table-shell"}>
      {!hideHeader && (
        <div className="app-section-header">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-semibold text-foreground">Open Positions</h3>
            <span className="rounded-full bg-muted/50 px-2 py-1 text-[10px] font-mono text-muted-foreground">
              {positions.length}
            </span>
          </div>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="app-table app-table-compact">
          <thead>
            <tr>
              {COLUMNS.map((col) => (
                <th key={col} className="whitespace-nowrap">
                  {col}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <PositionRow
                key={p.contract_symbol || p.symbol}
                position={p}
                onSelect={
                  onSelectPosition
                    ? () => onSelectPosition(p.symbol)
                    : undefined
                }
              />
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
