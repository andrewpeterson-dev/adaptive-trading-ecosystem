"use client";

import React from "react";
import { Receipt } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Order } from "@/types/trading";
import { EmptyState } from "@/components/ui/empty-state";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface TradeLogPanelProps {
  orders: Order[];
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const COLUMNS = [
  "Time",
  "Symbol",
  "Side",
  "Qty",
  "Type",
  "Status",
  "Fill Price",
] as const;

const MAX_ROWS = 20;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatTime(iso: string | null | undefined): string {
  if (!iso) return "\u2014";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "\u2014";
  const hours = String(d.getHours()).padStart(2, "0");
  const minutes = String(d.getMinutes()).padStart(2, "0");
  return `${hours}:${minutes}`;
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

function isLongDirection(dir: string): boolean {
  return (
    dir === "buy" ||
    dir === "long" ||
    dir === "buy_to_open" ||
    dir === "buy_to_close"
  );
}

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<string, string> = {
  filled: "text-emerald-400 bg-emerald-400/10",
  pending: "text-amber-400 bg-amber-400/10",
  new: "text-amber-400 bg-amber-400/10",
  accepted: "text-amber-400 bg-amber-400/10",
  partial: "text-amber-400 bg-amber-400/10",
  cancelled: "text-muted-foreground bg-muted/50",
  canceled: "text-muted-foreground bg-muted/50",
  expired: "text-muted-foreground bg-muted/50",
  rejected: "text-red-400 bg-red-400/10",
  failed: "text-red-400 bg-red-400/10",
};

function StatusBadge({ status }: { status: string }) {
  const normalized = status.toLowerCase();
  const style = STATUS_STYLES[normalized] || "text-muted-foreground bg-muted/50";
  return (
    <span className={cn("text-xs font-medium px-1.5 py-0.5 rounded capitalize", style)}>
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Side label
// ---------------------------------------------------------------------------

function SideLabel({ direction }: { direction: string }) {
  const isLong = isLongDirection(direction);
  return (
    <span
      className={cn(
        "text-xs font-bold uppercase",
        isLong ? "text-emerald-400" : "text-red-400"
      )}
    >
      {isLong ? "LONG" : "SHORT"}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Order row
// ---------------------------------------------------------------------------

function OrderRow({ order }: { order: Order }) {
  return (
    <tr className="border-b border-border/50 hover:bg-muted/30 transition-colors">
      {/* Time */}
      <td className="py-2.5 px-4 text-xs text-muted-foreground font-mono tabular-nums whitespace-nowrap">
        {formatTime(order.submitted_at)}
      </td>

      {/* Symbol */}
      <td className="py-2.5 px-4">
        <span className="font-mono font-bold text-sm">{order.symbol}</span>
      </td>

      {/* Side */}
      <td className="py-2.5 px-4">
        <SideLabel direction={order.direction} />
      </td>

      {/* Qty */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {order.quantity != null ? Math.abs(order.quantity) : "\u2014"}
      </td>

      {/* Type */}
      <td className="py-2.5 px-4 text-xs text-muted-foreground capitalize whitespace-nowrap">
        {order.order_type || "\u2014"}
      </td>

      {/* Status */}
      <td className="py-2.5 px-4">
        <StatusBadge status={order.status || "pending"} />
      </td>

      {/* Fill Price */}
      <td className="py-2.5 px-4 font-mono tabular-nums">
        {formatCurrency(order.filled_price)}
      </td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function TradeLogPanel({ orders }: TradeLogPanelProps) {
  const displayOrders = orders.slice(0, MAX_ROWS);

  if (orders.length === 0) {
    return (
      <div className="app-table-shell">
        <div className="app-section-header">
          <h3 className="text-sm font-semibold text-foreground">Trade Log</h3>
        </div>
        <EmptyState
          className="py-10"
          icon={<Receipt className="h-4 w-4 text-muted-foreground" />}
          title="No recent trades"
          description="Executed orders will appear here as they are processed."
        />
      </div>
    );
  }

  return (
    <div className="app-table-shell">
      <div className="app-section-header">
        <div className="flex items-center gap-2">
          <h3 className="text-sm font-semibold text-foreground">Trade Log</h3>
          <span className="rounded-full bg-muted/50 px-2 py-1 text-[10px] font-mono text-muted-foreground">
            {orders.length}
          </span>
        </div>
      </div>

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
            {displayOrders.map((order, i) => (
              <OrderRow key={order.id || `order-${i}`} order={order} />
            ))}
          </tbody>
        </table>
      </div>

      {orders.length > MAX_ROWS && (
        <div className="px-4 py-2 text-xs text-muted-foreground border-t border-border/50">
          Showing {MAX_ROWS} of {orders.length} orders
        </div>
      )}
    </div>
  );
}
