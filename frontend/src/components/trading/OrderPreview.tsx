"use client";

import React from "react";
import { useTradeStore } from "@/stores/trade-store";

interface OrderPreviewProps {
  quantity: number;
  price: number | null;
  direction: "buy" | "sell";
}

export function OrderPreview({ quantity, price, direction }: OrderPreviewProps) {
  const { account } = useTradeStore();

  if (quantity <= 0 || price == null || price <= 0) return null;
  if (!account) return null;

  const cost = quantity * price;
  const remainingCash = direction === "buy"
    ? account.cash - cost
    : account.cash + cost;
  const portfolioPct =
    account.portfolio_value > 0
      ? (cost / account.portfolio_value) * 100
      : null;

  return (
    <div className="rounded-md border border-border/50 bg-muted/30 px-3 py-2.5 space-y-1.5">
      <div className="text-[10px] font-semibold text-muted-foreground uppercase tracking-widest mb-1">
        Order Preview
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Est. Cost</span>
        <span className="font-mono tabular-nums font-medium">
          ${cost.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </span>
      </div>

      <div className="flex justify-between text-xs">
        <span className="text-muted-foreground">Remaining Cash</span>
        <span
          className={`font-mono tabular-nums font-medium ${
            remainingCash < 0 ? "text-red-400" : ""
          }`}
        >
          ${remainingCash.toLocaleString("en-US", {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}
        </span>
      </div>

      {portfolioPct != null && (
        <div className="flex justify-between text-xs">
          <span className="text-muted-foreground">% of Portfolio</span>
          <span className="font-mono tabular-nums font-medium">
            {portfolioPct.toFixed(1)}%
          </span>
        </div>
      )}
    </div>
  );
}
