"use client";

import { useMemo, useState } from "react";
import { ClipboardList, Search } from "lucide-react";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { useTradeStore } from "@/stores/trade-store";
import { formatCurrency, formatDateTime } from "@/lib/trading/format";

type SideFilter = "all" | "buy" | "sell";

function sideLabel(direction: string): "buy" | "sell" {
  return direction.toLowerCase().includes("buy") ? "buy" : "sell";
}

export function OpenOrdersPanel() {
  const orders = useTradeStore((state) => state.orders);
  const [search, setSearch] = useState("");
  const [sideFilter, setSideFilter] = useState<SideFilter>("all");

  const filteredOrders = useMemo(() => {
    return orders.filter((order) => {
      const symbolMatch = order.symbol.toUpperCase().includes(search.trim().toUpperCase());
      const sideMatch = sideFilter === "all" || sideLabel(order.direction) === sideFilter;
      return symbolMatch && sideMatch;
    });
  }, [orders, search, sideFilter]);

  return (
    <div className="app-panel p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            Open Orders
          </p>
          <p className="mt-1 text-sm font-medium text-foreground">
            Filter working orders without leaving the trading workspace.
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <div className="relative min-w-[200px]">
            <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Filter symbol"
              className="pl-9 font-mono"
            />
          </div>
          <div className="flex items-center gap-1 rounded-full border border-border/70 bg-muted/35 p-1">
            {(["all", "buy", "sell"] as SideFilter[]).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setSideFilter(value)}
                className={`rounded-full px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.14em] transition-colors ${
                  sideFilter === value
                    ? "bg-foreground text-background"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>
      </div>

      {filteredOrders.length === 0 ? (
        <EmptyState
          icon={<ClipboardList className="h-5 w-5 text-muted-foreground" />}
          title={orders.length === 0 ? "No open orders" : "No orders match the current filters"}
          description={
            orders.length === 0
              ? "Working orders will appear here when the connected broker reports them."
              : "Adjust the symbol or side filters to broaden the results."
          }
          className="py-10"
        />
      ) : (
        <div className="mt-4 overflow-hidden rounded-3xl border border-border/60">
          <div className="overflow-x-auto">
            <table className="app-table min-w-full">
              <thead>
                <tr>
                  <th>Symbol</th>
                  <th>Side</th>
                  <th>Type</th>
                  <th>Qty</th>
                  <th>Status</th>
                  <th>Limit</th>
                  <th>Stop</th>
                  <th>Submitted</th>
                </tr>
              </thead>
              <tbody>
                {filteredOrders.map((order) => (
                  <tr key={order.id}>
                    <td className="font-mono text-sm font-semibold">{order.symbol}</td>
                    <td className="capitalize">{sideLabel(order.direction)}</td>
                    <td className="uppercase">{order.order_type}</td>
                    <td className="font-mono tabular-nums">{order.quantity}</td>
                    <td>
                      <span className="rounded-full border border-border/70 bg-muted/35 px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        {order.status}
                      </span>
                    </td>
                    <td className="font-mono tabular-nums">{formatCurrency(order.limit_price)}</td>
                    <td className="font-mono tabular-nums">{formatCurrency(order.stop_price)}</td>
                    <td className="text-muted-foreground">{formatDateTime(order.submitted_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
